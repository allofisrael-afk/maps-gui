import os
from dotenv import load_dotenv

# טעינת משתני סביבה מתוך קובץ .env
load_dotenv()

def create_map():
    """
    פונקציה ליצירת קובץ HTML של המפה.
    המפה כוללת מפת חום, דקירת נקודות, והצגת נתוני מזג אוויר.
    """
    google_api_key = os.getenv('GOOGLE_API_KEY')
    map_file = "map.html"

    with open(map_file, "w", encoding="utf-8") as f:
        f.write(f"""
        <!DOCTYPE html>
        <html lang="he" dir="rtl">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>מפת גוגל משולבת</title>
            <style>
                #map {{
                    height: 100vh;
                    width: 100%;
                }}
                #status {{
                    position: absolute;
                    bottom: 10px;
                    left: 10px;
                    background-color: rgba(255, 255, 255, 0.7);
                    padding: 10px;
                    border-radius: 5px;
                    font-size: 14px;
                    color: black;
                    z-index: 1000;
                }}
                button {{
                    position: absolute;
                    top: 10px;
                    z-index: 1000;
                    padding: 10px;
                    margin: 5px;
                    background-color: #007bff;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    cursor: pointer;
                }}
                button:hover {{
                    background-color: #0056b3;
                }}
            </style>
        </head>
        <body>
            <div id="map"></div>
            <div id="status">מיקום העכבר: קו רוחב: 0.0000, קו אורך: 0.0000</div>
            <button onclick="toggleHeatmap()" style="left: 10px;">הפעל/כבה מפת חום</button>
            <button onclick="loadHeatmapDataFromCSV('weather_data.csv')">הוסף מפת חום</button>
            <script async defer
                src="https://maps.googleapis.com/maps/api/js?key={google_api_key}&callback=initMap&language=he&region=IL&libraries=visualization,marker">
            </script> 
            <script>
                var map;
                var heatmap;
                var heatmapData = [];

                function initMap() {{
                    map = new google.maps.Map(document.getElementById('map'), {{
                        center: {{ lat: 31.7683, lng: 35.2137 }},
                        zoom: 8
                    }});

                    heatmap = new google.maps.visualization.HeatmapLayer({{
                        data: heatmapData,
                        map: null,
                        radius: 50,
                        opacity: 0.6
                    }});

                    google.maps.event.addListener(map, 'mousemove', function(event) {{
                        var lat = event.latLng.lat().toFixed(4);
                        var lon = event.latLng.lng().toFixed(4);
                        document.getElementById('status').innerHTML = 
                            "מיקום העכבר: קו רוחב: " + lat + ", קו אורך: " + lon;
                    }});

                    google.maps.event.addListener(map, 'click', function(event) {{
                        var lat = event.latLng.lat().toFixed(4);
                        var lon = event.latLng.lng().toFixed(4);
                        fetchWeather(lat, lon);
                    }});
                }}

                function toggleHeatmap() {{
                    if (!heatmap) {{
                        console.error("Heatmap object is not initialized.");
                        alert("מפת החום לא הוגדרה.");
                        return;
                    }}
                    if (heatmap.getMap() === null) {{
                        loadHeatmapData();
                        heatmap.setMap(map);
                    }} else {{
                        heatmap.setMap(null);
                    }}
                }}

                function loadHeatmapData() {{
                    const url = "http://localhost:5002/heatmap_data";

                    fetch(url)
                        .then(response => {{
                            if (!response.ok) {{
                                throw new Error(`HTTP error! status: ${{response.status}}`);
                            }}
                            return response.json();
                        }})
                        .then(data => {{
                            heatmapData = data.map(point => {{
                                return {{
                                    location: new google.maps.LatLng(point.latitude, point.longitude),
                                    weight: point.temperature
                                }};
                            }});
                            heatmap.setData(heatmapData);
                        }})
                        .catch(error => {{
                            console.error("Error loading heatmap data:", error);
                            alert("שגיאה בטעינת נתוני מפת החום.");
                        }});
                }}

                function fetchWeather(lat, lon) {{
                    const url = `http://localhost:5002/weather?lat=${{lat}}&lon=${{lon}}`;

                    fetch(url)
                        .then(response => {{
                            if (!response.ok) {{
                                throw new Error(`HTTP error! status: ${{response.status}}`);
                            }}
                            return response.json();
                        }})
                        .then(data => {{
                            console.log("Response data:", data);

                            // ולידציה לשדות הדרושים בתשובה
                            if (!data.weather || !data.temperature) {{
                                throw new Error("הנתונים שהתקבלו מהשרת אינם כוללים את מזג האוויר או הטמפרטורה");
                            }}

                            // קריאה לפונקציה שמציגה את הנתונים על המפה
                            displayWeatherOnMap(lat, lon, data);
                        }})
                        .catch(error => {{
                            console.error("Error fetching weather data:", error.message);

                        // הצגת הודעת שגיאה, אך לא משפיעה על זרימת הקוד האחרת
                        alert("לא ניתן להחזיר נתוני מזג האוויר: " + error.message);
                        }});
                }}
                function displayWeatherOnMap(lat, lon, data) {{
                    try {{
                        // בדיקה אם הנתונים כוללים את המידע הדרוש
                        const weather = data.weather || "לא זמין"; // ברירת מחדל אם חסר
                        const temperature = data.temperature !== undefined ? `${{data.temperature}}°C` : "לא זמין"; // ברירת מחדל אם חסר
                
                        // תוכן להצגה ב-InfoWindow
                        const content = `
                            <div style="text-align: left; direction: rtl;">
                                <div><strong>קו רוחב:</strong> ${{lat}}</div>
                                <div><strong>קו אורך:</strong> ${{lon}}</div>
                                <div><strong>מזג אוויר:</strong> ${{weather}}</div>
                                <div><strong>טמפרטורה:</strong> ${{temperature}}</div>
                            </div>
                        `;
                
                        // יצירת InfoWindow עם התוכן
                        const infowindow = new google.maps.InfoWindow({{
                            content: content
                        }});
                
                        // יצירת מרקר עם המיקום
                        const marker = new google.maps.Marker({{
                            position: {{lat: parseFloat(lat), lng: parseFloat(lon)}},
                            map: map
                        }});
                               infowindow.open(map, marker);
                        // הגדרת אירוע "לחיצה" על המרקר להצגת ה-InfoWindow
                        marker.addListener("click", () => {{
                            infowindow.open(map, marker);
                        }});
                    }} catch (error) {{
                        console.error("Error displaying weather data on map:", error.message);
                    }}
                }}
                function loadHeatmapDataFromCSV(csvFilePath) {{
                    fetch(csvFilePath)
                        .then(response => response.text())
                        .then(csvText => {{
                            // פיצול השורות בקובץ ה-CSV
                            const rows = csvText.split("\n").filter(row => row.trim() !== "");
                            // הפקת הכותרות
                            const headers = rows[0].split(",");
                            const latitudeIndex = headers.indexOf("latitude");
                            const longitudeIndex = headers.indexOf("longitude");
                            const temperatureIndex = headers.indexOf("temperature");
                
                            if (latitudeIndex === -1 || longitudeIndex === -1 || temperatureIndex === -1) {{
                                throw new Error("קובץ ה-CSV לא מכיל את השדות הנדרשים: latitude, longitude, temperature.");
                                return;
                            }}
                
                            // עיבוד השורות לאחר הכותרת
                            const heatmapData = rows.slice(1).map(row => {{
                                const columns = row.split(",");
                                return {{
                                    location: new google.maps.LatLng(
                                        parseFloat(columns[latitudeIndex]),
                                        parseFloat(columns[longitudeIndex])
                                    ),
                                    weight: parseFloat(columns[temperatureIndex])
                                }};
                            }});
                
                            // יצירת שכבת HeatMap
                            const heatmapLayer = new google.maps.visualization.HeatmapLayer({{
                                data: heatmapData.map(point => ({{
                                    location: point.location,
                                    weight: point.weight
                                }})),
                                radius: 50,
                                opacity: 0.6
                            }});
                
                            // הוספת השכבה למפה
                            heatmapLayer.setMap(map);
                            console.log("שכבת HeatMap נוספה למפה בהצלחה.");
                        }}
                            console.error("שגיאה בטעינת נתוני HeatMap:", error);
                        }});
                }}
                .catch(error => {{
                    console.error("Error loading heatmap data:", error);
                }});
            }}
            </script>
        </body>
        </html>
        """)

    print(f"נוצרה מפה ושמה: {map_file}")


# קריאה לפונקציה ליצירת המפה
if __name__ == "__main__":
    create_map()
