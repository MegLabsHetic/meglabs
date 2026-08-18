import csv
import json
import random

# Real coordinates for Ecuador cities/provinces
COORDINATES = {
    "Ambato":       {"lat": -1.2417, "lon": -78.6197},
    "Cayambe":      {"lat":  0.0392, "lon": -78.1422},
    "Cotopaxi":     {"lat": -0.6833, "lon": -78.5833},
    "Cuenca":       {"lat": -2.8974, "lon": -79.0045},
    "Ecuador":      {"lat": -1.8312, "lon": -78.1834},  # Center of country
    "El Carmen":    {"lat":  0.2667, "lon": -79.4500},
    "Esmeraldas":   {"lat":  0.9592, "lon": -79.6539},
    "Guaranda":     {"lat": -1.5961, "lon": -79.0017},
    "Guayaquil":    {"lat": -2.1894, "lon": -79.8891},
    "Ibarra":       {"lat":  0.3392, "lon": -78.1222},
    "Imbabura":     {"lat":  0.3500, "lon": -78.1333},
    "Latacunga":    {"lat": -0.9333, "lon": -78.6167},
    "Libertad":     {"lat": -2.2333, "lon": -80.9000},
    "Loja":         {"lat": -3.9931, "lon": -79.2042},
    "Machala":      {"lat": -3.2581, "lon": -79.9554},
    "Manta":        {"lat": -0.9500, "lon": -80.7333},
    "Puyo":         {"lat": -1.4833, "lon": -78.0000},
    "Quevedo":      {"lat": -1.0225, "lon": -79.4608},
    "Quito":        {"lat": -0.1807, "lon": -78.4678},
    "Riobamba":     {"lat": -1.6635, "lon": -78.6547},
    "Salinas":      {"lat": -2.2000, "lon": -80.9667},
    "Santa Elena":  {"lat": -2.2260, "lon": -80.8593},
    "Santo Domingo": {"lat": -0.2532, "lon": -79.1719},
    "Santo Domingo de los Tsachilas": {"lat": -0.2532, "lon": -79.1719},
}

def make_random_geojson(lat, lon, locale_name):
    """Generate a random GeoJSON polygon around the given point (simulating a city boundary)."""
    random.seed(hash(locale_name))  # Reproducible per city

    # Random polygon with 5-8 vertices around the center point
    num_vertices = random.randint(5, 8)
    coords = []
    import math
    for i in range(num_vertices):
        angle = (2 * math.pi / num_vertices) * i + random.uniform(-0.3, 0.3)
        radius_lat = random.uniform(0.01, 0.05)
        radius_lon = random.uniform(0.01, 0.05)
        pt_lat = round(lat + radius_lat * math.sin(angle), 6)
        pt_lon = round(lon + radius_lon * math.cos(angle), 6)
        coords.append([pt_lon, pt_lat])
    # Close the polygon
    coords.append(coords[0])

    geojson = {
        "type": "Feature",
        "properties": {
            "name": locale_name
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [coords]
        }
    }
    return geojson

def main():
    input_file = "holidays_events.csv"
    output_file = "holidays_events_geo.csv"

    with open(input_file, "r", encoding="utf-8") as fin, \
         open(output_file, "w", encoding="utf-8", newline="") as fout:

        reader = csv.DictReader(fin)
        fieldnames = reader.fieldnames + ["latitude", "longitude", "geojson"]
        writer = csv.DictWriter(fout, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            locale_name = row["locale_name"].strip()

            if locale_name in COORDINATES:
                base_lat = COORDINATES[locale_name]["lat"]
                base_lon = COORDINATES[locale_name]["lon"]
                # Add small random jitter to make each row slightly unique
                lat = round(base_lat + random.uniform(-0.005, 0.005), 6)
                lon = round(base_lon + random.uniform(-0.005, 0.005), 6)
            else:
                # Fallback: random point in Ecuador
                base_lat = round(random.uniform(-4.0, 1.5), 6)
                base_lon = round(random.uniform(-81.0, -75.0), 6)
                lat = base_lat
                lon = base_lon

            geojson = make_random_geojson(base_lat, base_lon, locale_name)

            row["latitude"] = lat
            row["longitude"] = lon
            row["geojson"] = json.dumps(geojson, ensure_ascii=False)

            writer.writerow(row)

    print(f"Done! Enriched file saved as: {output_file}")
    print(f"Columns: {fieldnames}")

if __name__ == "__main__":
    main()
