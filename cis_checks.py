"""
בדיקות עמידה ב-CIS Microsoft Windows 11 Benchmark — Level 1 ו-Level 2, מסוננות לתת-קבוצה
שנבחרה כרלוונטית להקשר הפרויקט (שרתי Flask שמאזינים על פורטים מקומיים, הרצת תהליכי-בן,
מפתחות API מאוחסנים ב-.env, הורדת תלויות pip ובניית APK דרך PowerShell). כל בדיקה קוראת
בלבד (registry/PowerShell מקומי) ומחזירה SecurityFinding עם remediation — ההנחיה/פקודה
לתיקון אם הבדיקה נכשלה. חלק מהבדיקות (SMBv1, BitLocker) דורשות הרשאות מנהל לקריאה מלאה —
אם הריצה נכשלת מחוסר הרשאה, מדווח כ-info ("בדוק ידנית") ולא כממצא, כדי לא להציג false
positive. Level 2 הוא הקשחה עמוקה יותר (defense-in-depth) שחלק מהתיקונים המומלצים בה
כרוכים בפשרת שימושיות (למשל ביטול RDP לגמרי) — עדיין בדיקות read-only בלבד.
נצרך אך ורק ע"י security_checks.run_security_checks — לא רץ כ-CLI עצמאי.
"""
import json
import os
import subprocess
import tempfile
import time
import winreg
from pathlib import Path

from security_checks import SecurityFinding

_PS_TIMEOUT = 15


def _run_powershell(command, timeout=_PS_TIMEOUT):
    """ מריץ פקודת PowerShell יחידה ומחזיר את ה-stdout שלה, או None אם נכשלה/פג הזמן
    (כולל כישלון מחוסר הרשאות מנהל — נבדל מ"הערך הוא ריק" ע"י בדיקת הצלחת הרצה). """
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True, text=True, timeout=timeout
        )
        return proc.stdout.strip() if proc.returncode == 0 else None
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return None


def _read_registry_value(hive, path, name):
    """ קורא ערך (DWORD או מחרוזת) מהרישום. מחזיר None אם המפתח/הערך לא קיים — משמעו
    לרוב שהמדיניות לא הוגדרה במפורש, כלומר ברירת המחדל של Windows חלה (לרוב זה המצב
    הלא-מוקשח). """
    try:
        with winreg.OpenKey(hive, path) as key:
            value, _ = winreg.QueryValueEx(key, name)
            return value
    except (FileNotFoundError, OSError):
        return None


def _run_secedit_export():
    """ מייצא את מדיניות האבטחה המקומית (secedit) לקובץ זמני ומחזיר את תוכנו כטקסט —
    המקור היחיד למדיניות סיסמאות/נעילה, שלא נגיש דרך registry רגיל. """
    tmp_path = os.path.join(tempfile.gettempdir(), "cis_secpol_export.cfg")
    try:
        subprocess.run(["secedit", "/export", "/cfg", tmp_path, "/quiet"],
                        capture_output=True, timeout=_PS_TIMEOUT)
        if not os.path.exists(tmp_path):
            return None
        raw = Path(tmp_path).read_bytes()
        os.remove(tmp_path)
        encoding = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8"
        return raw.decode(encoding, errors="ignore")
    except (subprocess.SubprocessError, OSError):
        return None


def _parse_secedit_value(text, key):
    for line in text.splitlines():
        if line.strip().startswith(key + " "):
            _, _, value = line.partition("=")
            return value.strip()
    return None


def _check_firewall_enabled():
    check = "CIS L1: חומת אש (Windows Firewall) מופעלת בכל הפרופילים"
    out = _run_powershell("Get-NetFirewallProfile | Select-Object Name,Enabled | ConvertTo-Json -Compress")
    if out is None:
        return [SecurityFinding(check, "medium", True, "לא ניתן להריץ Get-NetFirewallProfile — בדוק ידנית")]
    try:
        profiles = json.loads(out)
        if isinstance(profiles, dict):
            profiles = [profiles]
        disabled = [p["Name"] for p in profiles if not p.get("Enabled")]
    except (json.JSONDecodeError, KeyError, TypeError):
        return [SecurityFinding(check, "medium", True, "פלט לא צפוי מ-PowerShell — בדוק ידנית")]
    if disabled:
        return [SecurityFinding(
            check, "high", False,
            f"הפרופילים הבאים כבויים: {', '.join(disabled)} — האפליקציה פותחת פורטים 5002-5004 "
            f"שיהיו חשופים יותר ללא חומת אש",
            remediation=f"הרץ כמנהל: Set-NetFirewallProfile -Profile {','.join(disabled)} -Enabled True")]
    return [SecurityFinding(check, "info", True, "כל הפרופילים (Domain/Private/Public) מופעלים")]


def _check_smb1_disabled():
    check = "CIS L1: פרוטוקול SMBv1 מבוטל"
    out = _run_powershell("(Get-WindowsOptionalFeature -Online -FeatureName SMB1Protocol).State")
    if out is None:
        return [SecurityFinding(check, "medium", True, "לא ניתן לבדוק (נדרשות הרשאות מנהל) — הרץ כמנהל לבדיקה מלאה")]
    if out.strip() == "Enabled":
        return [SecurityFinding(
            check, "medium", False,
            "SMBv1 מופעל — פרוטוקול ישן ופגיע (למשל EternalBlue/WannaCry) שאין סיבה להשאיר פעיל",
            remediation="הרץ כמנהל: Disable-WindowsOptionalFeature -Online -FeatureName SMB1Protocol -NoRestart")]
    return [SecurityFinding(check, "info", True, "SMBv1 מבוטל")]


def _check_llmnr_disabled():
    check = "CIS L1: LLMNR מבוטל"
    value = _read_registry_value(winreg.HKEY_LOCAL_MACHINE,
                                  r"SOFTWARE\Policies\Microsoft\Windows NT\DNSClient", "EnableMulticast")
    if value == 0:
        return [SecurityFinding(check, "info", True, "LLMNR מבוטל במדיניות")]
    return [SecurityFinding(
        check, "low", False,
        "LLMNR מופעל (ברירת המחדל) — חשוף להתקפות poisoning/spoofing ברשת המקומית שהמחשב מחובר אליה",
        remediation=r"הגדר ב-Registry: HKLM\SOFTWARE\Policies\Microsoft\Windows NT\DNSClient\EnableMulticast "
                    r"= 0 (DWORD), או ב-gpedit.msc: Computer Configuration > Administrative Templates > "
                    r"Network > DNS Client > Turn off multicast name resolution = Enabled")]


def _check_netbios_disabled():
    check = "CIS L1: NetBIOS over TCP/IP מבוטל"
    out = _run_powershell(
        "(Get-CimInstance Win32_NetworkAdapterConfiguration -Filter 'IPEnabled=True' "
        "| Select-Object -ExpandProperty TcpipNetbiosOptions) -join ','"
    )
    if not out:
        return [SecurityFinding(check, "low", True, "לא נמצאו מתאמי רשת פעילים לבדיקה, או שהבדיקה נכשלה")]
    values = [v.strip() for v in out.split(",") if v.strip()]
    not_disabled = [v for v in values if v != "2"]
    if not_disabled:
        return [SecurityFinding(
            check, "low", False,
            f"{len(not_disabled)} מתוך {len(values)} מתאמי רשת לא מבטלים NetBIOS במפורש",
            remediation="בכל מתאם רשת: מאפייני TCP/IPv4 > Advanced > WINS > Disable NetBIOS over TCP/IP, "
                        "או דרך PowerShell (כמנהל): Get-WmiObject Win32_NetworkAdapterConfiguration "
                        "-Filter 'IPEnabled=True' | ForEach-Object { $_.SetTcpipNetbios(2) }")]
    return [SecurityFinding(check, "info", True, "NetBIOS מבוטל בכל מתאמי הרשת הפעילים")]


def _check_guest_account_disabled():
    check = "CIS L1: חשבון Guest מבוטל"
    out = _run_powershell("(Get-LocalUser -Name Guest -ErrorAction SilentlyContinue).Enabled")
    if not out:
        return [SecurityFinding(check, "info", True, "חשבון Guest לא נמצא (כנראה כבר לא קיים במערכת)")]
    if out.strip().lower() == "true":
        return [SecurityFinding(
            check, "medium", False,
            "חשבון Guest פעיל — מאפשר כניסה למחשב ללא זיהוי משתמש ייעודי",
            remediation="הרץ כמנהל: Disable-LocalUser -Name Guest")]
    return [SecurityFinding(check, "info", True, "חשבון Guest מבוטל")]


def _check_uac_enabled():
    check = "CIS L1: User Account Control (UAC) מופעל"
    value = _read_registry_value(winreg.HKEY_LOCAL_MACHINE,
                                  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System", "EnableLUA")
    if value == 1:
        return [SecurityFinding(check, "info", True, "UAC מופעל")]
    return [SecurityFinding(
        check, "high", False,
        "UAC כבוי — כל תהליך (כולל תהליכי-הבן של שרתי ה-Flask שהאפליקציה מריצה) פועל ללא בקשת הרשאה מוגברת",
        remediation=r"הגדר ב-Registry: HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System\EnableLUA "
                    r"= 1 (DWORD) ואתחל את המחשב, או דרך לוח הבקרה: User Account Control Settings")]


def _check_password_policy():
    check = "CIS L1: מדיניות סיסמאות (אורך מינימלי, מורכבות)"
    text = _run_secedit_export()
    if text is None:
        return [SecurityFinding(check, "low", True, "לא ניתן לייצא מדיניות אבטחה מקומית (secedit) — בדוק ידנית")]
    min_len = _parse_secedit_value(text, "MinimumPasswordLength")
    complexity = _parse_secedit_value(text, "PasswordComplexity")
    problems = []
    if min_len is None or int(min_len) < 14:
        problems.append(f"אורך מינימלי לסיסמה: {min_len or '0'} (נדרש 14 ומעלה)")
    if complexity != "1":
        problems.append("דרישת מורכבות סיסמה כבויה")
    if problems:
        return [SecurityFinding(
            check, "medium", False, "; ".join(problems),
            remediation="secpol.msc > Account Policies > Password Policy: הגדר Minimum password length "
                        "ל-14 לפחות והפעל Password must meet complexity requirements")]
    return [SecurityFinding(check, "info", True, f"אורך מינימלי {min_len}, דרישת מורכבות מופעלת")]


def _check_account_lockout_policy():
    check = "CIS L1: מדיניות נעילת חשבון"
    text = _run_secedit_export()
    if text is None:
        return [SecurityFinding(check, "low", True, "לא ניתן לייצא מדיניות אבטחה מקומית (secedit) — בדוק ידנית")]
    threshold = _parse_secedit_value(text, "LockoutBadCount")
    if threshold is None or threshold == "0" or int(threshold) > 5:
        return [SecurityFinding(
            check, "medium", False,
            f"סף נעילת חשבון: {threshold or 'לא מוגדר (ללא הגבלה)'} — נדרש ערך בין 1 ל-5 ניסיונות כושלים",
            remediation="secpol.msc > Account Policies > Account Lockout Policy: הגדר Account lockout "
                        "threshold לערך בין 1-5")]
    return [SecurityFinding(check, "info", True, f"סף נעילה: {threshold} ניסיונות כושלים")]


def _check_defender_realtime():
    check = "CIS L1: Microsoft Defender — הגנה בזמן אמת מופעלת"
    out = _run_powershell("(Get-MpComputerStatus).RealTimeProtectionEnabled")
    if not out:
        return [SecurityFinding(check, "low", True,
                                 "לא ניתן לבדוק (Defender לא זמין/כבוי, או קיים AV צד-שלישי חלופי) — בדוק ידנית")]
    if out.strip().lower() == "true":
        return [SecurityFinding(check, "info", True, "הגנה בזמן אמת מופעלת")]
    return [SecurityFinding(
        check, "high", False,
        "הגנה בזמן אמת כבויה — הפרויקט מוריד תלויות pip ובונה APK; ללא אנטי-וירוס פעיל תלות זדונית לא תזוהה",
        remediation="הגדרות Windows > Privacy & Security > Windows Security > Virus & threat protection "
                    "> הפעל Real-time protection")]


def _check_windows_update_service():
    check = "CIS L1: שירות Windows Update פעיל"
    out = _run_powershell("(Get-Service -Name wuauserv).Status.ToString() + ',' + "
                           "(Get-Service -Name wuauserv).StartType.ToString()")
    if not out:
        return [SecurityFinding(check, "low", True, "לא ניתן לבדוק את שירות wuauserv")]
    status, _, start_type = out.strip().partition(",")
    if start_type.strip().lower() == "disabled":
        return [SecurityFinding(
            check, "medium", False, "שירות Windows Update מוגדר Disabled — עדכוני אבטחה לא יתקבלו",
            remediation="services.msc > Windows Update > Startup type: Manual/Automatic, ואז הפעל את השירות")]
    return [SecurityFinding(check, "info", True, f"שירות Windows Update: {status.strip()} (Startup: {start_type.strip()})")]


def _check_autorun_disabled():
    check = "CIS L1: AutoPlay/AutoRun מבוטל בכל סוגי הכוננים"
    value = _read_registry_value(winreg.HKEY_LOCAL_MACHINE,
                                  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer", "NoDriveTypeAutoRun")
    if value == 255:
        return [SecurityFinding(check, "info", True, "AutoRun מבוטל בכל סוגי הכוננים (0xFF)")]
    return [SecurityFinding(
        check, "low", False,
        f"AutoRun לא מבוטל באופן מלא (ערך נוכחי: {value if value is not None else 'לא מוגדר — ברירת מחדל'}) "
        f"— כונן USB זדוני יכול להיפתח/להריץ אוטומטית",
        remediation=r"הגדר ב-Registry: HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer"
                    r"\NoDriveTypeAutoRun = 255 (DWORD), או gpedit.msc: Computer Configuration > "
                    r"Administrative Templates > Windows Components > AutoPlay Policies > Turn off AutoPlay "
                    r"= Enabled (All drives)")]


def _check_powershell_logging():
    check = "CIS L1: PowerShell Script Block Logging מופעל"
    value = _read_registry_value(
        winreg.HKEY_LOCAL_MACHINE,
        r"SOFTWARE\Policies\Microsoft\Windows\PowerShell\ScriptBlockLogging", "EnableScriptBlockLogging")
    if value == 1:
        return [SecurityFinding(check, "info", True, "Script Block Logging מופעל")]
    return [SecurityFinding(
        check, "low", False,
        "Script Block Logging כבוי — build_apk.ps1 ופקודות PowerShell אחרות שהפרויקט מריץ לא יתועדו, "
        "מקשה על חקירת אירוע אם קוד זדוני ירוץ",
        remediation=r"הגדר ב-Registry: HKLM\SOFTWARE\Policies\Microsoft\Windows\PowerShell\ScriptBlockLogging"
                    r"\EnableScriptBlockLogging = 1 (DWORD), או gpedit.msc: Administrative Templates > "
                    r"Windows Components > Windows PowerShell > Turn on PowerShell Script Block Logging")]


def _check_rdp_nla():
    check = "CIS L1: חיבורי Remote Desktop דורשים NLA"
    deny = _read_registry_value(winreg.HKEY_LOCAL_MACHINE,
                                 r"SYSTEM\CurrentControlSet\Control\Terminal Server", "fDenyTSConnections")
    if deny == 1:
        return [SecurityFinding(check, "info", True, "Remote Desktop כבוי לגמרי — הבדיקה לא רלוונטית")]
    nla = _read_registry_value(
        winreg.HKEY_LOCAL_MACHINE,
        r"SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp", "UserAuthentication")
    if nla == 1:
        return [SecurityFinding(check, "info", True, "RDP מופעל עם דרישת NLA")]
    return [SecurityFinding(
        check, "medium", False,
        "RDP מופעל ללא דרישת Network Level Authentication — חושף להתקפות brute-force על מסך הכניסה ללא אימות מקדים",
        remediation=r"הגדר ב-Registry: HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations"
                    r"\RDP-Tcp\UserAuthentication = 1 (DWORD), או System Properties > Remote > Allow "
                    r"connections only from computers running Remote Desktop with NLA")]


def _check_inactivity_lock():
    check = "CIS L1: נעילת מסך אוטומטית לאחר חוסר פעילות"
    value = _read_registry_value(
        winreg.HKEY_LOCAL_MACHINE,
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System", "InactivityTimeoutSecs")
    if value is not None and 0 < value <= 900:
        return [SecurityFinding(check, "info", True, f"נעילה אוטומטית לאחר {value} שניות חוסר פעילות")]
    return [SecurityFinding(
        check, "low", False,
        "אין הגבלת חוסר-פעילות למכונה (או שהיא מעל 900 שניות) — מחשב שנשאר פתוח ללא השגחה נגיש לכל מי שניגש אליו פיזית",
        remediation=r"הגדר ב-Registry: HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
                    r"\InactivityTimeoutSecs = 900 (DWORD) או פחות, או secpol.msc: Local Policies > "
                    r"Security Options > Interactive logon: Machine inactivity limit")]


def _check_wdigest_disabled():
    check = "CIS L2: WDigest Authentication מבוטל"
    value = _read_registry_value(winreg.HKEY_LOCAL_MACHINE,
                                  r"SYSTEM\CurrentControlSet\Control\SecurityProviders\WDigest", "UseLogonCredential")
    if value == 0:
        return [SecurityFinding(check, "info", True, "WDigest מבוטל — סיסמאות לא נשמרות בטקסט גלוי בזיכרון")]
    state = "מופעל במפורש" if value == 1 else "לא מוגדר במפורש"
    return [SecurityFinding(
        check, "high", False,
        f"WDigest {state} — סיסמאות עלולות להישמר בטקסט גלוי בזיכרון וניתנות לחילוץ בכלים כמו Mimikatz; "
        f"המחשב הזה מחזיק מפתחות API רגישים",
        remediation=r"הגדר ב-Registry: HKLM\SYSTEM\CurrentControlSet\Control\SecurityProviders\WDigest"
                    r"\UseLogonCredential = 0 (DWORD), או gpedit.msc: Administrative Templates > "
                    r"MS Security Guide > WDigest Authentication = Disabled")]


def _check_lsa_protection():
    check = "CIS L2: LSA Protection (RunAsPPL) מופעל"
    value = _read_registry_value(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Lsa", "RunAsPPL")
    if value == 1:
        return [SecurityFinding(check, "info", True, "LSA Protection מופעל — תהליך LSASS מוגן כתהליך מוגן (PPL)")]
    return [SecurityFinding(
        check, "high", False,
        "LSA Protection כבוי — תהליך LSASS פגיע לחילוץ אישורים/סודות מהזיכרון בכלים כמו Mimikatz",
        remediation=r"הגדר ב-Registry: HKLM\SYSTEM\CurrentControlSet\Control\Lsa\RunAsPPL = 1 (DWORD) ואתחל "
                    r"את המחשב (ודא תאימות דרייברים/EDR לפני הפעלה בסביבת production)")]


def _check_lm_hash_disabled():
    check = "CIS L2: אחסון LM hash מבוטל"
    value = _read_registry_value(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Lsa", "NoLMHash")
    if value == 1:
        return [SecurityFinding(check, "info", True, "אחסון LM hash מבוטל")]
    return [SecurityFinding(
        check, "low", False,
        "המפתח NoLMHash לא מוגדר במפורש — גרסאות Windows עדכניות כבר לא מייצרות LM hash כברירת מחדל, "
        "אך המדיניות לא נאכפת במפורש",
        remediation=r"הגדר ב-Registry: HKLM\SYSTEM\CurrentControlSet\Control\Lsa\NoLMHash = 1 (DWORD), "
                    r"או secpol.msc: Network security: Do not store LAN Manager hash value on next password change")]


def _check_always_install_elevated_disabled():
    check = "CIS L2: AlwaysInstallElevated מבוטל (HKLM + HKCU)"
    hklm = _read_registry_value(winreg.HKEY_LOCAL_MACHINE,
                                 r"SOFTWARE\Policies\Microsoft\Windows\Installer", "AlwaysInstallElevated")
    hkcu = _read_registry_value(winreg.HKEY_CURRENT_USER,
                                 r"SOFTWARE\Policies\Microsoft\Windows\Installer", "AlwaysInstallElevated")
    if hklm == 1 and hkcu == 1:
        return [SecurityFinding(
            check, "high", False,
            "AlwaysInstallElevated מופעל בשני ה-hives — כל משתמש יכול להתקין חבילות MSI בהרשאות SYSTEM; "
            "וקטור הסלמת הרשאות ידוע, במיוחד רלוונטי בסביבה שמריצה build/install (pip, APK)",
            remediation=r"מחק או אפס ל-0 את שני הערכים: HKLM\SOFTWARE\Policies\Microsoft\Windows\Installer"
                        r"\AlwaysInstallElevated וגם HKCU\...\AlwaysInstallElevated, או gpedit.msc: "
                        r"Windows Installer > Always install with elevated privileges = Disabled")]
    return [SecurityFinding(check, "info", True, "AlwaysInstallElevated אינו מופעל (ברירת מחדל בטוחה)")]


def _check_restrict_anonymous_sam():
    check = "CIS L2: הגבלת מנייה אנונימית של חשבונות SAM"
    value = _read_registry_value(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Lsa", "RestrictAnonymousSAM")
    if value is None or value == 1:
        return [SecurityFinding(check, "info", True, "מנייה אנונימית של חשבונות מוגבלת (ברירת מחדל מודרנית, או מוגדר במפורש)")]
    return [SecurityFinding(
        check, "medium", False,
        "RestrictAnonymousSAM מוגדר במפורש ל-0 — מאפשר למשתמשים אנונימיים ברשת למנות את רשימת חשבונות המשתמשים המקומיים",
        remediation=r"הגדר ב-Registry: HKLM\SYSTEM\CurrentControlSet\Control\Lsa\RestrictAnonymousSAM = 1 (DWORD), "
                    r"או secpol.msc: Network access: Do not allow anonymous enumeration of SAM accounts")]


def _check_restrict_remote_sam():
    check = "CIS L2: הגבלת גישה מרוחקת ל-SAM (RestrictRemoteSAM)"
    value = _read_registry_value(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Lsa", "RestrictRemoteSAM")
    if value is None:
        return [SecurityFinding(check, "info", True,
                                 "המפתח לא מוגדר — ברירת המחדל בגרסאות Windows עדכניות כבר מגבילה גישה מרוחקת ל-Administrators בלבד")]
    if str(value).strip() == "":
        return [SecurityFinding(
            check, "medium", False, "המפתח מוגדר לערך ריק — מסיר את ההגבלה על גישה מרוחקת ל-SAM",
            remediation=r"הגדר ב-Registry: HKLM\SYSTEM\CurrentControlSet\Control\Lsa\RestrictRemoteSAM = "
                        r'"O:BAG:BAD:(A;;RC;;;BA)" (REG_SZ), או secpol.msc: Network access: Restrict clients '
                        r"allowed to make remote calls to SAM")]
    return [SecurityFinding(check, "info", True, f"המפתח מוגדר: {value}")]


def _check_smb_signing_required():
    check = "CIS L2: חתימת SMB נדרשת (Client + Server)"
    client = _read_registry_value(winreg.HKEY_LOCAL_MACHINE,
                                   r"SYSTEM\CurrentControlSet\Services\LanmanWorkstation\Parameters", "RequireSecuritySignature")
    server = _read_registry_value(winreg.HKEY_LOCAL_MACHINE,
                                   r"SYSTEM\CurrentControlSet\Services\LanmanServer\Parameters", "RequireSecuritySignature")
    missing = [name for name, value in (("Client", client), ("Server", server)) if value != 1]
    if missing:
        return [SecurityFinding(
            check, "medium", False,
            f"חתימת SMB לא נדרשת עבור: {', '.join(missing)} — חושף לתקיפות MITM/שיבוש תעבורה ברשת המקומית "
            f"(שים לב: הפעלה עלולה להאט/לשבש שיתופי קבצים ישנים ברשת אם קיימים)",
            remediation=r"הגדר ב-Registry: HKLM\SYSTEM\CurrentControlSet\Services\LanmanWorkstation\Parameters"
                        r"\RequireSecuritySignature = 1 וגם HKLM\...\LanmanServer\Parameters"
                        r"\RequireSecuritySignature = 1 (DWORD כל אחד), או secpol.msc: Microsoft network "
                        r"client/server: Digitally sign communications (always)")]
    return [SecurityFinding(check, "info", True, "חתימת SMB נדרשת גם ב-Client וגם ב-Server")]


def _check_wsh_disabled():
    check = "CIS L2: Windows Script Host מבוטל"
    value = _read_registry_value(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows Script Host\Settings", "Enabled")
    if value == 0:
        return [SecurityFinding(check, "info", True, "Windows Script Host מבוטל")]
    return [SecurityFinding(
        check, "low", False,
        "Windows Script Host מופעל (ברירת המחדל) — מאפשר הרצת קבצי .vbs/.js זדוניים ללא אזהרה",
        remediation=r"הגדר ב-Registry: HKLM\SOFTWARE\Microsoft\Windows Script Host\Settings\Enabled = 0 (DWORD)")]


def _check_rdp_disabled_entirely():
    check = "CIS L2: Remote Desktop מבוטל לחלוטין"
    deny = _read_registry_value(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Terminal Server", "fDenyTSConnections")
    if deny == 1:
        return [SecurityFinding(check, "info", True, "Remote Desktop מבוטל לחלוטין")]
    return [SecurityFinding(
        check, "medium", False,
        "Remote Desktop מופעל — האפליקציה עצמה לא נזקקת ל-RDP; כל שירות מאזין נוסף מגדיל את משטח התקיפה של המחשב",
        remediation=r"הגדר ב-Registry: HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server"
                    r"\fDenyTSConnections = 1 (DWORD), או System Properties > Remote > Don't allow remote "
                    r"connections to this computer (השאר מופעל אם בפועל נדרשת גישת RDP למחשב הזה)")]


def _check_bitlocker_enabled():
    check = "CIS L2: הצפנת כונן המערכת (BitLocker) מופעלת"
    out = _run_powershell("(Get-BitLockerVolume -MountPoint C: -ErrorAction Stop).ProtectionStatus.ToString()")
    if not out:
        return [SecurityFinding(check, "low", True,
                                 "לא ניתן לבדוק (BitLocker אינו זמין במהדורת Windows הזו, או נדרשות הרשאות מנהל)")]
    if out.strip() == "On":
        return [SecurityFinding(check, "info", True, "הצפנת BitLocker פעילה על כונן המערכת")]
    return [SecurityFinding(
        check, "medium", False,
        "כונן המערכת אינו מוצפן — קובץ .env עם מפתחות API חשוף בטקסט גלוי אם המחשב/הדיסק נגנב",
        remediation="הגדרות Windows > Privacy & Security > Device encryption (או לוח הבקרה > BitLocker "
                    "Drive Encryption) > הפעל הצפנה. דורש TPM ו/או הרשאות מנהל")]


def _check_smartscreen_enabled():
    check = "CIS L2: Microsoft Defender SmartScreen מופעל (Explorer)"
    value = _read_registry_value(winreg.HKEY_CURRENT_USER,
                                  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer", "SmartScreenEnabled")
    if value is None:
        return [SecurityFinding(check, "info", True, "לא מוגדר במפורש — ברירת המחדל של Windows היא מופעל")]
    if str(value).strip().lower() == "off":
        return [SecurityFinding(
            check, "medium", False,
            "SmartScreen כבוי — לא תוצג אזהרה לפני הרצת קובץ שהורד מהאינטרנט (רלוונטי בהורדת תלויות/כלים לפרויקט)",
            remediation=r"הגדר ב-Registry: HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer"
                        r'\SmartScreenEnabled = "Warn" (REG_SZ), או Windows Security > App & browser control '
                        r"> Reputation-based protection settings")]
    return [SecurityFinding(check, "info", True, f"SmartScreen מוגדר: {value}")]


def _run_checks(check_fns, on_progress=None):
    """ מריץ רשימת פונקציות בדיקה ומחזיר SecurityFinding אחד מרוכז לכל אחת, עם elapsed_ms. """
    findings = []
    for check_fn in check_fns:
        start = time.perf_counter()
        results = check_fn()
        elapsed = (time.perf_counter() - start) * 1000
        for finding in results:
            finding.elapsed_ms = elapsed
            findings.append(finding)
            if on_progress:
                on_progress(finding)
    return findings


_L1_CHECKS = (
    _check_firewall_enabled,
    _check_smb1_disabled,
    _check_llmnr_disabled,
    _check_netbios_disabled,
    _check_guest_account_disabled,
    _check_uac_enabled,
    _check_password_policy,
    _check_account_lockout_policy,
    _check_defender_realtime,
    _check_windows_update_service,
    _check_autorun_disabled,
    _check_powershell_logging,
    _check_rdp_nla,
    _check_inactivity_lock,
)

_L2_CHECKS = (
    _check_wdigest_disabled,
    _check_lsa_protection,
    _check_lm_hash_disabled,
    _check_always_install_elevated_disabled,
    _check_restrict_anonymous_sam,
    _check_restrict_remote_sam,
    _check_smb_signing_required,
    _check_wsh_disabled,
    _check_rdp_disabled_entirely,
    _check_bitlocker_enabled,
    _check_smartscreen_enabled,
)


def run_cis_l1_checks(on_progress=None):
    """ מריץ את בדיקות ה-CIS Level 1 שנבחרו ומחזיר רשימת SecurityFinding — נצרך ע"י
    security_checks.run_security_checks כמו כל בדיקה אחרת. """
    return _run_checks(_L1_CHECKS, on_progress)


def run_cis_l2_checks(on_progress=None):
    """ מריץ את בדיקות ה-CIS Level 2 שנבחרו (הקשחה עמוקה יותר) ומחזיר רשימת SecurityFinding. """
    return _run_checks(_L2_CHECKS, on_progress)
