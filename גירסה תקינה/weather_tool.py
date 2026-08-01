import math  # ייבוא ספרייה לחישובים מתמטיים, כולל מרחקים גיאוגרפיים
import csv  # ייבוא ספרייה לקריאה וכתיבה של קבצי CSV
import requests  # ייבוא ספרייה לשליחת בקשות HTTP לשרתים
import pandas as pd  # ייבוא ספרייה לעיבוד נתונים בפורמט טבלאי
import folium  # ייבוא ספרייה ליצירת מפות אינטראקטיביות
from tqdm import tqdm  # ייבוא ספרייה להצגת סרגל התקדמות
from folium.plugins import HeatMap  # ייבוא מודול ליצירת שכבת HeatMap במפות Folium

# פונקציה לספירת נקודות בתוך רדיוס נתון
def count_points_in_radius(radius_km=10, step_km=1):
    """
    מחשבת את כמות הנקודות שנמצאות בתוך רדיוס נתון בפסיעות קבועות.
    :param radius_km: רדיוס (בקילומטרים)
    :param step_km: גודל הפסיעה (בקילומטרים)
    :return: כמות הנקודות ברדיוס
    """
    steps = int(radius_km / step_km)  # חישוב מספר הפסיעות
    count = 0  # מונה הנקודות
    for i in range(-steps, steps + 1):  # לולאה על השורות ברשת
        for j in range(-steps, steps + 1):  # לולאה על העמודות ברשת
            if math.sqrt(i**2 + j**2) <= steps:  # בדיקה אם הנקודה נמצאת בתוך הרדיוס
                count += 1
    return count

# בדיקת כמות הנקודות ברדיוס של 20 ק"מ עם פסיעות של 5 ק"מ
print("Number of points:", count_points_in_radius(radius_km=10, step_km=1))

# פונקציה ליצירת רשימת קואורדינטות סביב נקודה מרכזית
def generate_coordinates(lat, lon, radius_km=1, step_km=1):
    """
    מייצרת רשימת קואורדינטות ברדיוס מסוים סביב נקודה נתונה.
    :param lat: קו רוחב מרכזי
    :param lon: קו אורך מרכזי
    :param radius_km: רדיוס (בקילומטרים)
    :param step_km: גודל הפסיעה (בקילומטרים)
    :return: רשימת קואורדינטות [(lat, lon), ...]
    """
    coordinates = []  # רשימה לאחסון הקואורדינטות
    steps = int(radius_km / step_km)  # חישוב מספר הפסיעות
    for i in range(-steps, steps + 1):  # לולאה על השורות ברשת
        for j in range(-steps, steps + 1):  # לולאה על העמודות ברשת
            if math.sqrt(i**2 + j**2) <= steps:  # בדיקה אם הנקודה נמצאת בתוך הרדיוס
                delta_lat = i * step_km / 111  # המרחק בקו רוחב
                delta_lon = j * step_km / (111 * math.cos(math.radians(lat)))  # המרחק בקו אורך
                coordinates.append((lat + delta_lat, lon + delta_lon))  # הוספת הקואורדינטה לרשימה
    return coordinates

# פונקציה לשליחת בקשת מזג אוויר לשרת עבור קואורדינטות נתונות
def fetch_weather_data(lat, lon):
    """
    שולחת בקשה לשרת לקבלת נתוני מזג אוויר עבור נקודה מסוימת.
    :param lat: קו רוחב
    :param lon: קו אורך
    :return: תגובת השרת כדיקט
    """
    base_url = "http://localhost:5002/weather"  # כתובת ה-API של השרת
    try:
        print(f"Requesting data for LAT={lat}, LON={lon}")  # הודעה על שליחת הבקשה
        response = requests.get(f"{base_url}?lat={lat}&lon={lon}")  # שליחת בקשת HTTP
        print(f"Response Status: {response.status_code}")  # הדפסת סטטוס התגובה
        if response.status_code == 200:  # אם התגובה תקינה
            print(f"Response Data: {response.json()}")  # הדפסת הנתונים שהתקבלו
            return response.json()  # החזרת הנתונים
        else:
            print(f"Failed to fetch data for LAT={lat}, LON={lon}. Status code: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error fetching data for LAT={lat}, LON={lon}: {e}")  # טיפול בשגיאה
        return None

# פונקציה לשליחת בקשות מזג אוויר עם סרגל התקדמות
def fetch_weather_data_with_tqdm(coordinates):
    """
    שולחת בקשות לשרת עבור רשימת קואורדינטות ומציגה סרגל התקדמות.
    :param coordinates: רשימת קואורדינטות [(lat, lon), ...]
    :return: רשימת תגובות מהשרת
    """
    weather_data = []  # רשימה לאחסון הנתונים
    for lat, lon in tqdm(coordinates, desc="Fetching Weather Data"):  # לולאה עם סרגל התקדמות
        data = fetch_weather_data(lat, lon)  # שליחת בקשת מזג אוויר
        if data:
            weather_data.append(data)  # הוספת התגובה לרשימה
    return weather_data

# פונקציה לשמירת נתוני מזג האוויר בקובץ CSV
def save_weather_data(weather_data, filename="weather_data.csv"):
    """
    שומרת את נתוני מזג האוויר לקובץ CSV.
    :param weather_data: רשימת נתוני מזג האוויר
    :param filename: שם הקובץ לשמירה
    """
    with open(filename, "w", newline='', encoding="utf-8") as csvfile:
        fieldnames = ["latitude", "longitude", "temperature", "weather"]  # שמות העמודות בקובץ
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()  # כתיבת כותרת העמודות
        for data in weather_data:
            writer.writerow(data)  # כתיבת כל שורה לקובץ
    print(f"Weather data saved to {filename}")

# פונקציה ליצירת מפת חום מתוך קובץ CSV
def create_heatmap_from_csv(csv_file, output_html="heatmap.html"):
    """
    יוצרת מפת חום מבוססת נתוני מזג אוויר מתוך קובץ CSV.
    :param csv_file: נתיב לקובץ ה-CSV
    :param output_html: שם קובץ ה-HTML שיכיל את מפת החום
    """
    data = pd.read_csv(csv_file)  # קריאת הנתונים מקובץ ה-CSV

    required_columns = {"latitude", "longitude", "temperature"}  # עמודות נדרשות
    if not required_columns.issubset(data.columns):  # בדיקה שהעמודות קיימות
        raise ValueError(f"Missing required columns in CSV. Expected: {required_columns}")

    heat_data = [
        [row["latitude"], row["longitude"], row["temperature"]]  # יצירת רשימה ל-HeatMap
        for _, row in data.iterrows()
    ]

    center_lat = data["latitude"].mean()  # חישוב קו רוחב מרכזי
    center_lon = data["longitude"].mean()  # חישוב קו אורך מרכזי
    heatmap_map = folium.Map(location=[center_lat, center_lon], zoom_start=12)  # יצירת המפה

    # הוספת שכבת HeatMap למפה
    HeatMap(
        heat_data,
        gradient={
            0.2: "blue",   # טמפרטורות נמוכות
            0.5: "yellow", # טמפרטורות ממוצעות
            1.0: "red"     # טמפרטורות גבוהות
        },
        min_opacity=0.1,
        radius=45,
        blur=15
    ).add_to(heatmap_map)

    heatmap_map.save(output_html)  # שמירת המפה לקובץ HTML
    print(f"Heatmap saved to {output_html}")

# פונקציה ראשית לניהול התהליך
def main():
    """
    הפונקציה הראשית שמנהלת את כל השלבים:
    - יצירת קואורדינטות
    - שליחת בקשות וקבלת נתוני מזג האוויר
    - שמירת הנתונים בקובץ
    - יצירת מפת חום
    """
    center_lat = 31.7683  # קו רוחב מרכזי לדוגמה
    center_lon = 35.2137  # קו אורך מרכזי לדוגמה

    print("Generating coordinates...")
    coordinates = generate_coordinates(center_lat, center_lon, radius_km=10, step_km=1)  # יצירת קואורדינטות

    print("Fetching weather data...")
    weather_data = fetch_weather_data_with_tqdm(coordinates)  # שליחת בקשות וקבלת נתונים

    save_weather_data(weather_data, filename="weather_data.csv")  # שמירת הנתונים
    print("Weather data saved successfully.")

    create_heatmap_from_csv("weather_data.csv", output_html="heatmap.html")  # יצירת מפת חום

# הפעלת התהליך הראשי
if __name__ == "__main__":
    main()
