import logging  # ייבוא מודול הלוגים
import requests  # ייבוא מודול לשליחת בקשות HTTP
import asyncio  # ייבוא מודול לתמיכה בפונקציות א-סינכרוניות

# הגדרת הלוגing בתחילת הקובץ
logging.basicConfig(filename='app_combined.log', level=logging.INFO, format='%(asctime)s - %(message)s')


async def fetch_weather_data_async(region_name):
    """
    שולחת בקשת GET א-סינכרונית לשרת ה-API לקבלת נתוני מזג אוויר עבור אזור מסוים.
    :param region_name: שם האזור שברצונך לקבל עבורו את נתוני מזג האוויר.
    :return: נתוני מזג האוויר אם התקבלה תשובה תקינה, אחרת מבנה ריק.
    """
    try:
        # יצירת כתובת ה-API עם פרמטר של שם האזור
        url = f"http://localhost:5002/weather?region={region_name}"

        # ביצוע קריאה א-סינכרונית עם הגבלת זמן
        response = await asyncio.to_thread(requests.get, url, timeout=5)  # קריאה לא-סינכרונית

        # אם יש שגיאה בסטטוס, נחזיר מבנה ריק
        if response.status_code == 200:
            return response.json()
        else:
            logging.error(f"שגיאה בקבלת מזג האוויר עבור {region_name}")
            return {}
    except requests.exceptions.Timeout:
        logging.error(f"שגיאה: חיבור לשרת ה-API נכשל - זמן קצוב.")
        return {}
    except requests.exceptions.ConnectionError:
        logging.error("שגיאה: השרת אינו זמין.")
        return {}
    except Exception as e:
        logging.error(f"שגיאה בתקשורת עם שרת ה-API: {e}")
        return {}


def fetch_geo_data(location="Tel Aviv"):
    """
    שולחת בקשה לשרת הגיאוגרפי לקבלת מידע על מיקום גיאוגרפי עבור עיר מסוימת.
    :param location: המיקום (ברירת מחדל: תל אביב)
    :return: מידע גיאוגרפי אם התקבל בהצלחה, אחרת מבנה ריק.
    """
    try:
        # יצירת כתובת ה-API עם פרמטר של מיקום
        url = f"http://localhost:5003/geo_data?location={location}"
        response = requests.get(url, timeout=5)  # הגבלת זמן לתגובה של 5 שניות

        # העלאת שגיאה אם יש בעיית HTTP
        response.raise_for_status()

        return response.json()  # החזרת הנתונים שהתקבלו
    except requests.exceptions.ConnectionError:
        logging.error("שגיאה: השרת הגיאוגרפי אינו זמין.")
        return {}
    except requests.exceptions.Timeout:
        logging.error("שגיאה: חיבור לשרת הגיאוגרפי נכשל - זמן קצוב.")
        return {}
    except Exception as e:
        logging.error(f"שגיאה כללית: {e}")
        return {}


def fetch_weather_data(region_name):
    """
    שולחת בקשה לשרת ה-API לקבלת נתוני מזג אוויר עבור אזור מסוים.
    :param region_name: שם האזור שברצונך לקבל עבורו את נתוני מזג האוויר.
    :return: נתוני מזג האוויר אם התקבלה תשובה תקינה, אחרת מבנה ריק.
    """
    try:
        # יצירת כתובת ה-API עם פרמטר של שם האזור
        url = f"http://localhost:5002/weather?region={region_name}"

        # שליחת בקשת GET לשרת עם הגבלת זמן
        response = requests.get(url, timeout=5)

        # אם יש שגיאה בסטטוס, נחזיר מבנה ריק
        if response.status_code == 200:
            return response.json()
        else:
            logging.error(f"שגיאה בקבלת מזג האוויר עבור {region_name}")
            return {}
    except requests.exceptions.Timeout:
        logging.error(f"שגיאה: חיבור לשרת ה-API נכשל - זמן קצוב.")
        return {}
    except requests.exceptions.ConnectionError:
        logging.error("שגיאה: השרת אינו זמין.")
        return {}
    except Exception as e:
        logging.error(f"שגיאה בתקשורת עם שרת ה-API: {e}")
        return {}
