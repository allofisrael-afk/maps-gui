import urllib.request  # לשליחת בקשות HTTP

def send_request(lat, lon):
    """
    פונקציה לשליחת בקשה לשרת ולתיעוד התוצאה.
    :param lat: קו רוחב
    :param lon: קו אורך
    """
    try:
        url = f"http://localhost:5002/weather?lat={lat}&lon={lon}"
        print(f"שולח בקשה לכתובת: {url}")
        with urllib.request.urlopen(url) as response:
            if response.status == 200:
                print(f"תשובה התקבלה עבור LAT={lat}, LON={lon}")
            else:
                print(f"שגיאה: סטטוס {response.status}")
    except Exception as e:
        print(f"שגיאה בשליחת בקשה עבור LAT={lat}, LON={lon}: {e}")

# שליחת 5 בקשות בודדות
def test_multiple_requests():
    """
    שליחת 5 בקשות לשרת לנ"צ שונים ובדיקת התוצאות.
    """
    print("** מתחילים את הבדיקה **")
    for i in range(15):
        lat = 31.5 + i * 0.01
        lon = 34.8 + i * 0.01
        send_request(lat, lon)
    print("** הבדיקה הסתיימה **")

if __name__ == "__main__":
    test_multiple_requests()
