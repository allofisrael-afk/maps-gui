import logging
import os
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests

load_dotenv()

logging.basicConfig(filename='app_combined.log', level=logging.INFO, format='%(asctime)s - %(message)s')

app = Flask(__name__)
# תיקון: CORS מוגבל ל-localhost בלבד
CORS(app, origins=["null", "http://localhost", "http://127.0.0.1"])

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

_MAX_LOCATION_LEN = 200  # תיקון: מגבלת אורך לפרמטר location


@app.route("/geo_data", methods=["GET"])
def get_geo_data():
    location = request.args.get("location", "").strip()

    if not location:
        logging.error("חסר פרמטר 'location'")
        return jsonify({"error": "יש לספק פרמטר 'location'"}), 400

    # תיקון: וולידציה על אורך הקלט
    if len(location) > _MAX_LOCATION_LEN:
        logging.warning("פרמטר location ארוך מדי")
        return jsonify({"error": "פרמטר 'location' ארוך מדי"}), 400

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": location, "key": GOOGLE_API_KEY}

    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()

        data = response.json()

        if data["status"] == "OK":
            result = data["results"][0]
            return jsonify({
                "address":   result["formatted_address"],
                "latitude":  result["geometry"]["location"]["lat"],
                "longitude": result["geometry"]["location"]["lng"]
            })
        else:
            logging.error(f"שגיאה במענה מ-Google API: {data.get('status')}")
            return jsonify({"error": "מיקום לא נמצא"}), 404

    except requests.exceptions.Timeout:
        logging.error("שגיאה: הזמן שהוקצב לחיבור פג")
        return jsonify({"error": "שגיאה: הזמן שהוקצב לחיבור פג"}), 408

    except requests.exceptions.RequestException as e:
        logging.error(f"שגיאה בחיבור ל-Google API: {str(e)}")
        # תיקון: הודעה גנרית ל-client, פרטים רק בלוג
        return jsonify({"error": "שגיאה פנימית בשרת"}), 500


if __name__ == "__main__":
    # תיקון: debug=False + קישור ל-127.0.0.1 בלבד
    app.run(host='127.0.0.1', port=5003, debug=False)
