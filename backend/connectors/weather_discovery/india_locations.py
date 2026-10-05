"""
SkyPulse India Regional Location Database
==========================================
Comprehensive structured location reference for:
  - All 28 States + 8 Union Territories
  - ~250 key districts across India
  - Major cities/towns with lat/lon centroids
  - Region groupings for discovery targeting

Used by the query_engine to generate LOCATION × EVENT × LANGUAGE search queries.
"""

import re
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# State / UT Canonical Registry
# ---------------------------------------------------------------------------

INDIA_STATES: Dict[str, Dict] = {
    "andhra_pradesh":   {"name": "Andhra Pradesh",       "abbr": "AP",  "lat": 15.9129, "lon": 79.7400, "capital": "Amaravati"},
    "arunachal_pradesh":{"name": "Arunachal Pradesh",    "abbr": "AR",  "lat": 28.2180, "lon": 94.7278, "capital": "Itanagar"},
    "assam":            {"name": "Assam",                 "abbr": "AS",  "lat": 26.2006, "lon": 92.9376, "capital": "Dispur"},
    "bihar":            {"name": "Bihar",                 "abbr": "BR",  "lat": 25.0961, "lon": 85.3131, "capital": "Patna"},
    "chhattisgarh":     {"name": "Chhattisgarh",         "abbr": "CG",  "lat": 21.2787, "lon": 81.8661, "capital": "Raipur"},
    "goa":              {"name": "Goa",                   "abbr": "GA",  "lat": 15.2993, "lon": 74.1240, "capital": "Panaji"},
    "gujarat":          {"name": "Gujarat",               "abbr": "GJ",  "lat": 22.2587, "lon": 71.1924, "capital": "Gandhinagar"},
    "haryana":          {"name": "Haryana",               "abbr": "HR",  "lat": 29.0588, "lon": 76.0856, "capital": "Chandigarh"},
    "himachal_pradesh": {"name": "Himachal Pradesh",      "abbr": "HP",  "lat": 31.1048, "lon": 77.1734, "capital": "Shimla"},
    "jharkhand":        {"name": "Jharkhand",             "abbr": "JH",  "lat": 23.6102, "lon": 85.2799, "capital": "Ranchi"},
    "karnataka":        {"name": "Karnataka",             "abbr": "KA",  "lat": 15.3173, "lon": 75.7139, "capital": "Bengaluru"},
    "kerala":           {"name": "Kerala",                "abbr": "KL",  "lat": 10.8505, "lon": 76.2711, "capital": "Thiruvananthapuram"},
    "madhya_pradesh":   {"name": "Madhya Pradesh",        "abbr": "MP",  "lat": 22.9734, "lon": 78.6569, "capital": "Bhopal"},
    "maharashtra":      {"name": "Maharashtra",           "abbr": "MH",  "lat": 19.7515, "lon": 75.7139, "capital": "Mumbai"},
    "manipur":          {"name": "Manipur",               "abbr": "MN",  "lat": 24.6637, "lon": 93.9063, "capital": "Imphal"},
    "meghalaya":        {"name": "Meghalaya",             "abbr": "ML",  "lat": 25.4670, "lon": 91.3662, "capital": "Shillong"},
    "mizoram":          {"name": "Mizoram",               "abbr": "MZ",  "lat": 23.1645, "lon": 92.9376, "capital": "Aizawl"},
    "nagaland":         {"name": "Nagaland",              "abbr": "NL",  "lat": 26.1584, "lon": 94.5624, "capital": "Kohima"},
    "odisha":           {"name": "Odisha",                "abbr": "OD",  "lat": 20.9517, "lon": 85.0985, "capital": "Bhubaneswar"},
    "punjab":           {"name": "Punjab",                "abbr": "PB",  "lat": 31.1471, "lon": 75.3412, "capital": "Chandigarh"},
    "rajasthan":        {"name": "Rajasthan",             "abbr": "RJ",  "lat": 27.0238, "lon": 74.2179, "capital": "Jaipur"},
    "sikkim":           {"name": "Sikkim",                "abbr": "SK",  "lat": 27.5330, "lon": 88.5122, "capital": "Gangtok"},
    "tamil_nadu":       {"name": "Tamil Nadu",            "abbr": "TN",  "lat": 11.1271, "lon": 78.6569, "capital": "Chennai"},
    "telangana":        {"name": "Telangana",             "abbr": "TS",  "lat": 18.1124, "lon": 79.0193, "capital": "Hyderabad"},
    "tripura":          {"name": "Tripura",               "abbr": "TR",  "lat": 23.9408, "lon": 91.9882, "capital": "Agartala"},
    "uttar_pradesh":    {"name": "Uttar Pradesh",         "abbr": "UP",  "lat": 26.8467, "lon": 80.9462, "capital": "Lucknow"},
    "uttarakhand":      {"name": "Uttarakhand",           "abbr": "UK",  "lat": 30.0668, "lon": 79.0193, "capital": "Dehradun"},
    "west_bengal":      {"name": "West Bengal",           "abbr": "WB",  "lat": 22.9868, "lon": 87.8550, "capital": "Kolkata"},
    # Union Territories
    "andaman_nicobar":  {"name": "Andaman & Nicobar Islands", "abbr": "AN", "lat": 11.7401, "lon": 92.6586, "capital": "Port Blair"},
    "chandigarh_ut":    {"name": "Chandigarh",            "abbr": "CH",  "lat": 30.7333, "lon": 76.7794, "capital": "Chandigarh"},
    "dadra_nh":         {"name": "Dadra & Nagar Haveli and Daman & Diu", "abbr": "DN", "lat": 20.1809, "lon": 73.0169, "capital": "Daman"},
    "delhi":            {"name": "Delhi",                  "abbr": "DL",  "lat": 28.6139, "lon": 77.2090, "capital": "New Delhi"},
    "jammu_kashmir":    {"name": "Jammu & Kashmir",       "abbr": "JK",  "lat": 33.7782, "lon": 76.5762, "capital": "Srinagar"},
    "ladakh":           {"name": "Ladakh",                 "abbr": "LA",  "lat": 34.1526, "lon": 77.5770, "capital": "Leh"},
    "lakshadweep":      {"name": "Lakshadweep",           "abbr": "LD",  "lat": 10.5667, "lon": 72.6417, "capital": "Kavaratti"},
    "puducherry":       {"name": "Puducherry",             "abbr": "PY",  "lat": 11.9416, "lon": 79.8083, "capital": "Puducherry"},
}


# ---------------------------------------------------------------------------
# District Registry (key districts per state, ~250 entries)
# ---------------------------------------------------------------------------

INDIA_DISTRICTS: List[Dict] = [
    # Andhra Pradesh
    {"district": "Visakhapatnam",   "state": "Andhra Pradesh",   "lat": 17.6868, "lon": 83.2185},
    {"district": "Vijayawada",      "state": "Andhra Pradesh",   "lat": 16.5062, "lon": 80.6480},
    {"district": "Guntur",          "state": "Andhra Pradesh",   "lat": 16.2991, "lon": 80.4575},
    {"district": "Tirupati",        "state": "Andhra Pradesh",   "lat": 13.6288, "lon": 79.4192},
    {"district": "Kurnool",         "state": "Andhra Pradesh",   "lat": 15.8281, "lon": 78.0373},
    {"district": "Nellore",         "state": "Andhra Pradesh",   "lat": 14.4426, "lon": 79.9865},
    # Assam
    {"district": "Kamrup",          "state": "Assam",            "lat": 26.1445, "lon": 91.7362},
    {"district": "Dibrugarh",       "state": "Assam",            "lat": 27.4728, "lon": 94.9120},
    {"district": "Jorhat",          "state": "Assam",            "lat": 26.7465, "lon": 94.2026},
    {"district": "Silchar",         "state": "Assam",            "lat": 24.8333, "lon": 92.7789},
    {"district": "Tezpur",          "state": "Assam",            "lat": 26.6338, "lon": 92.7956},
    {"district": "Barpeta",         "state": "Assam",            "lat": 26.3222, "lon": 91.0000},
    {"district": "Nagaon",          "state": "Assam",            "lat": 26.3466, "lon": 92.6844},
    # Bihar
    {"district": "Patna",           "state": "Bihar",            "lat": 25.5941, "lon": 85.1376},
    {"district": "Muzaffarpur",     "state": "Bihar",            "lat": 26.1197, "lon": 85.3910},
    {"district": "Gaya",            "state": "Bihar",            "lat": 24.7955, "lon": 84.9994},
    {"district": "Bhagalpur",       "state": "Bihar",            "lat": 25.2425, "lon": 86.9842},
    {"district": "Darbhanga",       "state": "Bihar",            "lat": 26.1542, "lon": 85.8918},
    {"district": "Saharsa",         "state": "Bihar",            "lat": 25.8768, "lon": 86.5992},
    {"district": "Purnia",          "state": "Bihar",            "lat": 25.7771, "lon": 87.4753},
    # Chhattisgarh
    {"district": "Raipur",          "state": "Chhattisgarh",     "lat": 21.2514, "lon": 81.6296},
    {"district": "Bilaspur",        "state": "Chhattisgarh",     "lat": 22.0797, "lon": 82.1391},
    {"district": "Durg",            "state": "Chhattisgarh",     "lat": 21.1904, "lon": 81.2849},
    {"district": "Korba",           "state": "Chhattisgarh",     "lat": 22.3595, "lon": 82.7501},
    # Gujarat
    {"district": "Ahmedabad",       "state": "Gujarat",          "lat": 23.0225, "lon": 72.5714},
    {"district": "Surat",           "state": "Gujarat",          "lat": 21.1702, "lon": 72.8311},
    {"district": "Vadodara",        "state": "Gujarat",          "lat": 22.3072, "lon": 73.1812},
    {"district": "Rajkot",          "state": "Gujarat",          "lat": 22.3039, "lon": 70.8022},
    {"district": "Bhavnagar",       "state": "Gujarat",          "lat": 21.7645, "lon": 72.1519},
    {"district": "Kutch",           "state": "Gujarat",          "lat": 23.7337, "lon": 69.8597},
    {"district": "Anand",           "state": "Gujarat",          "lat": 22.5645, "lon": 72.9289},
    {"district": "Gandhinagar",     "state": "Gujarat",          "lat": 23.2156, "lon": 72.6369},
    # Haryana
    {"district": "Gurugram",        "state": "Haryana",          "lat": 28.4595, "lon": 77.0266},
    {"district": "Faridabad",       "state": "Haryana",          "lat": 28.4089, "lon": 77.3178},
    {"district": "Panipat",         "state": "Haryana",          "lat": 29.3909, "lon": 76.9635},
    {"district": "Ambala",          "state": "Haryana",          "lat": 30.3782, "lon": 76.7767},
    {"district": "Hisar",           "state": "Haryana",          "lat": 29.1492, "lon": 75.7217},
    {"district": "Rohtak",          "state": "Haryana",          "lat": 28.8955, "lon": 76.6066},
    # Himachal Pradesh
    {"district": "Shimla",          "state": "Himachal Pradesh", "lat": 31.1048, "lon": 77.1734},
    {"district": "Kullu",           "state": "Himachal Pradesh", "lat": 31.9592, "lon": 77.1089},
    {"district": "Manali",          "state": "Himachal Pradesh", "lat": 32.2396, "lon": 77.1887},
    {"district": "Mandi",           "state": "Himachal Pradesh", "lat": 31.7085, "lon": 76.9318},
    {"district": "Kangra",          "state": "Himachal Pradesh", "lat": 32.0998, "lon": 76.2691},
    {"district": "Dharamsala",      "state": "Himachal Pradesh", "lat": 32.2190, "lon": 76.3234},
    # Jharkhand
    {"district": "Ranchi",          "state": "Jharkhand",        "lat": 23.3441, "lon": 85.3096},
    {"district": "Jamshedpur",      "state": "Jharkhand",        "lat": 22.8046, "lon": 86.2029},
    {"district": "Dhanbad",         "state": "Jharkhand",        "lat": 23.7957, "lon": 86.4304},
    {"district": "Bokaro",          "state": "Jharkhand",        "lat": 23.6693, "lon": 86.1511},
    # Karnataka
    {"district": "Bengaluru",       "state": "Karnataka",        "lat": 12.9716, "lon": 77.5946},
    {"district": "Mysuru",          "state": "Karnataka",        "lat": 12.2958, "lon": 76.6394},
    {"district": "Mangaluru",       "state": "Karnataka",        "lat": 12.9141, "lon": 74.8560},
    {"district": "Hubli-Dharwad",   "state": "Karnataka",        "lat": 15.3647, "lon": 75.1240},
    {"district": "Belagavi",        "state": "Karnataka",        "lat": 15.8497, "lon": 74.4977},
    {"district": "Shivamogga",      "state": "Karnataka",        "lat": 13.9299, "lon": 75.5681},
    {"district": "Udupi",           "state": "Karnataka",        "lat": 13.3409, "lon": 74.7421},
    {"district": "Kodagu",          "state": "Karnataka",        "lat": 12.3375, "lon": 75.8069},
    # Kerala
    {"district": "Thiruvananthapuram", "state": "Kerala",        "lat":  8.5241, "lon": 76.9366},
    {"city": "Kochi", "district": "Ernakulam", "state": "Kerala", "lat":  9.9312, "lon": 76.2673},
    {"district": "Ernakulam",       "state": "Kerala",           "lat":  9.9816, "lon": 76.2999},
    {"district": "Kozhikode",       "state": "Kerala",           "lat": 11.2588, "lon": 75.7804},
    {"district": "Thrissur",        "state": "Kerala",           "lat": 10.5276, "lon": 76.2144},
    {"district": "Kannur",          "state": "Kerala",           "lat": 11.8745, "lon": 75.3704},
    {"district": "Idukki",          "state": "Kerala",           "lat":  9.9189, "lon": 77.1025},
    {"district": "Wayanad",         "state": "Kerala",           "lat": 11.6854, "lon": 76.1320},
    {"district": "Malappuram",      "state": "Kerala",           "lat": 11.0730, "lon": 76.0740},
    {"district": "Alappuzha",       "state": "Kerala",           "lat":  9.4981, "lon": 76.3388},
    # Madhya Pradesh
    {"district": "Bhopal",          "state": "Madhya Pradesh",   "lat": 23.2599, "lon": 77.4126},
    {"district": "Indore",          "state": "Madhya Pradesh",   "lat": 22.7196, "lon": 75.8577},
    {"district": "Jabalpur",        "state": "Madhya Pradesh",   "lat": 23.1815, "lon": 79.9864},
    {"district": "Gwalior",         "state": "Madhya Pradesh",   "lat": 26.2183, "lon": 78.1828},
    {"district": "Ujjain",          "state": "Madhya Pradesh",   "lat": 23.1793, "lon": 75.7849},
    {"district": "Sagar",           "state": "Madhya Pradesh",   "lat": 23.8388, "lon": 78.7378},
    # Maharashtra
    {"city": "Mumbai", "district": "Mumbai City", "state": "Maharashtra", "lat": 19.0760, "lon": 72.8777},
    {"district": "Mumbai",          "state": "Maharashtra",      "lat": 19.0760, "lon": 72.8777},
    {"district": "Pune",            "state": "Maharashtra",      "lat": 18.5204, "lon": 73.8567},
    {"district": "Nagpur",          "state": "Maharashtra",      "lat": 21.1458, "lon": 79.0882},
    {"district": "Nashik",          "state": "Maharashtra",      "lat": 19.9975, "lon": 73.7898},
    {"district": "Aurangabad",      "state": "Maharashtra",      "lat": 19.8762, "lon": 75.3433},
    {"district": "Thane",           "state": "Maharashtra",      "lat": 19.2183, "lon": 72.9781},
    {"district": "Kolhapur",        "state": "Maharashtra",      "lat": 16.7050, "lon": 74.2433},
    {"district": "Solapur",         "state": "Maharashtra",      "lat": 17.6599, "lon": 75.9064},
    {"district": "Konkan",          "state": "Maharashtra",      "lat": 16.7000, "lon": 73.3000},
    {"district": "Amravati",        "state": "Maharashtra",      "lat": 20.9374, "lon": 77.7796},
    {"district": "Ratnagiri",       "state": "Maharashtra",      "lat": 16.9902, "lon": 73.3120},
    # Manipur
    {"district": "Imphal",          "state": "Manipur",          "lat": 24.8170, "lon": 93.9368},
    # Meghalaya
    {"district": "Shillong",        "state": "Meghalaya",        "lat": 25.5788, "lon": 91.8933},
    {"district": "Cherrapunji",     "state": "Meghalaya",        "lat": 25.2895, "lon": 91.7348},
    # Odisha (All 30 Official Districts + Key Cities)
    {"city": "Bhubaneswar", "district": "Khordha", "state": "Odisha", "lat": 20.2961, "lon": 85.8245},
    {"district": "Khordha",         "state": "Odisha",           "lat": 20.1818, "lon": 85.6200},
    {"district": "Khurda",          "state": "Odisha",           "lat": 20.1818, "lon": 85.6200},
    {"city": "Cuttack", "district": "Cuttack", "state": "Odisha", "lat": 20.4625, "lon": 85.8828},
    {"district": "Cuttack",         "state": "Odisha",           "lat": 20.4625, "lon": 85.8828},
    {"city": "Puri", "district": "Puri", "state": "Odisha",      "lat": 19.8135, "lon": 85.8312},
    {"district": "Puri",            "state": "Odisha",           "lat": 19.8135, "lon": 85.8312},
    {"district": "Angul",           "state": "Odisha",           "lat": 20.8444, "lon": 85.1511},
    {"district": "Balangir",        "state": "Odisha",           "lat": 20.7109, "lon": 83.4867},
    {"district": "Bolanir",         "state": "Odisha",           "lat": 20.7109, "lon": 83.4867},
    {"district": "Balasore",        "state": "Odisha",           "lat": 21.4942, "lon": 86.9360},
    {"district": "Baleswar",        "state": "Odisha",           "lat": 21.4942, "lon": 86.9360},
    {"district": "Bargarh",         "state": "Odisha",           "lat": 21.3333, "lon": 83.6167},
    {"district": "Bhadrak",         "state": "Odisha",           "lat": 21.0544, "lon": 86.5000},
    {"district": "Boudh",           "state": "Odisha",           "lat": 20.8333, "lon": 84.3167},
    {"district": "Deogarh",         "state": "Odisha",           "lat": 21.5333, "lon": 84.7333},
    {"district": "Debagarh",        "state": "Odisha",           "lat": 21.5333, "lon": 84.7333},
    {"district": "Dhenkanal",       "state": "Odisha",           "lat": 20.6667, "lon": 85.6000},
    {"district": "Gajapati",        "state": "Odisha",           "lat": 18.8100, "lon": 84.1500},
    {"district": "Ganjam",          "state": "Odisha",           "lat": 19.3800, "lon": 85.0500},
    {"city": "Berhampur", "district": "Ganjam", "state": "Odisha", "lat": 19.3150, "lon": 84.7941},
    {"city": "Chhatrapur", "district": "Ganjam", "state": "Odisha", "lat": 19.3500, "lon": 84.9833},
    {"district": "Jagatsinghpur",   "state": "Odisha",           "lat": 20.2500, "lon": 86.1700},
    {"district": "Jajpur",          "state": "Odisha",           "lat": 20.8500, "lon": 86.3300},
    {"district": "Jharsuguda",      "state": "Odisha",           "lat": 21.8500, "lon": 84.0167},
    {"district": "Kalahandi",       "state": "Odisha",           "lat": 19.9000, "lon": 83.1667},
    {"city": "Bhawanipatna", "district": "Kalahandi", "state": "Odisha", "lat": 19.9000, "lon": 83.1667},
    {"district": "Kandhamal",       "state": "Odisha",           "lat": 20.4700, "lon": 84.2300},
    {"city": "Phulbani", "district": "Kandhamal", "state": "Odisha", "lat": 20.4700, "lon": 84.2300},
    {"district": "Kendrapara",      "state": "Odisha",           "lat": 20.5015, "lon": 86.4199},
    {"district": "Kendujhar",       "state": "Odisha",           "lat": 21.6300, "lon": 85.5800},
    {"district": "Keonjhar",        "state": "Odisha",           "lat": 21.6300, "lon": 85.5800},
    {"district": "Koraput",         "state": "Odisha",           "lat": 18.8130, "lon": 82.7120},
    {"city": "Jeypore", "district": "Koraput", "state": "Odisha", "lat": 18.8500, "lon": 82.5800},
    {"district": "Malkangiri",      "state": "Odisha",           "lat": 18.3500, "lon": 81.9000},
    {"district": "Mayurbhanj",      "state": "Odisha",           "lat": 21.9300, "lon": 86.7300},
    {"city": "Baripada", "district": "Mayurbhanj", "state": "Odisha", "lat": 21.9300, "lon": 86.7300},
    {"district": "Nabarangpur",     "state": "Odisha",           "lat": 19.2300, "lon": 82.5500},
    {"district": "Nawarangpur",     "state": "Odisha",           "lat": 19.2300, "lon": 82.5500},
    {"district": "Nayagarh",        "state": "Odisha",           "lat": 20.1300, "lon": 85.1000},
    {"district": "Nuapada",         "state": "Odisha",           "lat": 20.8300, "lon": 82.5200},
    {"district": "Rayagada",        "state": "Odisha",           "lat": 19.1700, "lon": 83.4200},
    {"district": "Sambalpur",       "state": "Odisha",           "lat": 21.4700, "lon": 83.9812},
    {"district": "Subarnapur",      "state": "Odisha",           "lat": 20.8300, "lon": 83.9200},
    {"district": "Sonepur",         "state": "Odisha",           "lat": 20.8300, "lon": 83.9200},
    {"district": "Sundargarh",      "state": "Odisha",           "lat": 22.1200, "lon": 84.0300},
    {"city": "Rourkela", "district": "Sundargarh", "state": "Odisha", "lat": 22.2492, "lon": 84.8828},
    # Punjab
    {"district": "Amritsar",        "state": "Punjab",           "lat": 31.6340, "lon": 74.8723},
    {"district": "Ludhiana",        "state": "Punjab",           "lat": 30.9010, "lon": 75.8573},
    {"district": "Jalandhar",       "state": "Punjab",           "lat": 31.3260, "lon": 75.5762},
    {"district": "Patiala",         "state": "Punjab",           "lat": 30.3398, "lon": 76.3869},
    {"district": "Bathinda",        "state": "Punjab",           "lat": 30.2110, "lon": 74.9455},
    # Rajasthan
    {"district": "Jaipur",          "state": "Rajasthan",        "lat": 26.9124, "lon": 75.7873},
    {"district": "Jodhpur",         "state": "Rajasthan",        "lat": 26.2389, "lon": 73.0243},
    {"district": "Bikaner",         "state": "Rajasthan",        "lat": 28.0229, "lon": 73.3119},
    {"district": "Udaipur",         "state": "Rajasthan",        "lat": 24.5854, "lon": 73.7125},
    {"district": "Kota",            "state": "Rajasthan",        "lat": 25.2138, "lon": 75.8648},
    {"district": "Ajmer",           "state": "Rajasthan",        "lat": 26.4499, "lon": 74.6399},
    {"district": "Barmer",          "state": "Rajasthan",        "lat": 25.7521, "lon": 71.3967},
    # Tamil Nadu
    {"district": "Chennai",         "state": "Tamil Nadu",       "lat": 13.0827, "lon": 80.2707},
    {"district": "Coimbatore",      "state": "Tamil Nadu",       "lat": 11.0168, "lon": 76.9558},
    {"district": "Madurai",         "state": "Tamil Nadu",       "lat":  9.9252, "lon": 78.1198},
    {"district": "Salem",           "state": "Tamil Nadu",       "lat": 11.6643, "lon": 78.1460},
    {"district": "Trichy",          "state": "Tamil Nadu",       "lat": 10.7905, "lon": 78.7047},
    {"district": "Tirunelveli",     "state": "Tamil Nadu",       "lat":  8.7139, "lon": 77.7567},
    {"district": "Vellore",         "state": "Tamil Nadu",       "lat": 12.9165, "lon": 79.1325},
    {"district": "Nilgiris",        "state": "Tamil Nadu",       "lat": 11.4916, "lon": 76.7337},
    {"district": "Kanyakumari",     "state": "Tamil Nadu",       "lat":  8.0883, "lon": 77.5385},
    {"district": "Cuddalore",       "state": "Tamil Nadu",       "lat": 11.7480, "lon": 79.7714},
    {"district": "Nagapattinam",    "state": "Tamil Nadu",       "lat": 10.7672, "lon": 79.8449},
    # Telangana
    {"district": "Hyderabad",       "state": "Telangana",        "lat": 17.3850, "lon": 78.4867},
    {"district": "Warangal",        "state": "Telangana",        "lat": 17.9784, "lon": 79.5941},
    {"district": "Karimnagar",      "state": "Telangana",        "lat": 18.4386, "lon": 79.1288},
    {"district": "Nizamabad",       "state": "Telangana",        "lat": 18.6725, "lon": 78.0941},
    {"district": "Khammam",         "state": "Telangana",        "lat": 17.2473, "lon": 80.1514},
    # Uttar Pradesh
    {"district": "Lucknow",         "state": "Uttar Pradesh",    "lat": 26.8467, "lon": 80.9462},
    {"district": "Kanpur",          "state": "Uttar Pradesh",    "lat": 26.4499, "lon": 80.3319},
    {"district": "Varanasi",        "state": "Uttar Pradesh",    "lat": 25.3176, "lon": 82.9739},
    {"district": "Agra",            "state": "Uttar Pradesh",    "lat": 27.1767, "lon": 78.0081},
    {"district": "Prayagraj",       "state": "Uttar Pradesh",    "lat": 25.4358, "lon": 81.8463},
    {"district": "Meerut",          "state": "Uttar Pradesh",    "lat": 28.9845, "lon": 77.7064},
    {"district": "Gorakhpur",       "state": "Uttar Pradesh",    "lat": 26.7606, "lon": 83.3732},
    {"district": "Bareilly",        "state": "Uttar Pradesh",    "lat": 28.3670, "lon": 79.4304},
    {"district": "Aligarh",         "state": "Uttar Pradesh",    "lat": 27.8974, "lon": 78.0880},
    {"district": "Jhansi",          "state": "Uttar Pradesh",    "lat": 25.4484, "lon": 78.5685},
    # Uttarakhand
    {"district": "Dehradun",        "state": "Uttarakhand",      "lat": 30.3165, "lon": 78.0322},
    {"district": "Haridwar",        "state": "Uttarakhand",      "lat": 29.9457, "lon": 78.1642},
    {"district": "Nainital",        "state": "Uttarakhand",      "lat": 29.3803, "lon": 79.4636},
    {"district": "Chamoli",         "state": "Uttarakhand",      "lat": 30.4002, "lon": 79.3212},
    {"district": "Pithoragarh",     "state": "Uttarakhand",      "lat": 29.5819, "lon": 80.2180},
    {"district": "Uttarkashi",      "state": "Uttarakhand",      "lat": 30.7268, "lon": 78.4354},
    {"district": "Rudraprayag",     "state": "Uttarakhand",      "lat": 30.2855, "lon": 78.9813},
    # West Bengal
    {"district": "Kolkata",         "state": "West Bengal",      "lat": 22.5726, "lon": 88.3639},
    {"district": "Howrah",          "state": "West Bengal",      "lat": 22.5958, "lon": 88.2636},
    {"district": "Darjeeling",      "state": "West Bengal",      "lat": 27.0360, "lon": 88.2627},
    {"district": "Siliguri",        "state": "West Bengal",      "lat": 26.7271, "lon": 88.3953},
    {"district": "Jalpaiguri",      "state": "West Bengal",      "lat": 26.5449, "lon": 88.7179},
    {"district": "Murshidabad",     "state": "West Bengal",      "lat": 24.1800, "lon": 88.2700},
    {"district": "Malda",           "state": "West Bengal",      "lat": 25.0108, "lon": 88.1400},
    {"district": "Midnapore",       "state": "West Bengal",      "lat": 22.4190, "lon": 87.3190},
    {"district": "Sundarbans",      "state": "West Bengal",      "lat": 21.9497, "lon": 88.8995},
    {"district": "Cooch Behar",     "state": "West Bengal",      "lat": 26.3234, "lon": 89.4486},
    # Delhi / NCR
    {"district": "New Delhi",       "state": "Delhi",            "lat": 28.6139, "lon": 77.2090},
    {"district": "Noida",           "state": "Uttar Pradesh",    "lat": 28.5355, "lon": 77.3910},
    {"district": "Ghaziabad",       "state": "Uttar Pradesh",    "lat": 28.6692, "lon": 77.4538},
    # Jammu & Kashmir / Ladakh
    {"district": "Srinagar",        "state": "Jammu & Kashmir",  "lat": 34.0837, "lon": 74.7973},
    {"district": "Jammu",           "state": "Jammu & Kashmir",  "lat": 32.7266, "lon": 74.8570},
    {"district": "Leh",             "state": "Ladakh",           "lat": 34.1526, "lon": 77.5770},
    {"district": "Kargil",          "state": "Ladakh",           "lat": 34.5539, "lon": 76.1349},
    # North-East
    {"district": "Agartala",        "state": "Tripura",          "lat": 23.8315, "lon": 91.2868},
    {"district": "Aizawl",          "state": "Mizoram",          "lat": 23.7307, "lon": 92.7173},
    {"district": "Kohima",          "state": "Nagaland",         "lat": 25.6751, "lon": 94.1086},
    {"district": "Itanagar",        "state": "Arunachal Pradesh","lat": 27.0844, "lon": 93.6053},
    {"district": "Gangtok",         "state": "Sikkim",           "lat": 27.3389, "lon": 88.6065},
    # Coastal / Island
    {"district": "Port Blair",      "state": "Andaman & Nicobar","lat": 11.6234, "lon": 92.7265},
    {"district": "Kavaratti",       "state": "Lakshadweep",      "lat": 10.5626, "lon": 72.6369},
]


# ---------------------------------------------------------------------------
# High-Priority Discovery Locations (subset used for frequent polling)
# ---------------------------------------------------------------------------

HIGH_PRIORITY_LOCATIONS: List[str] = [
    # Metros & National Hubs
    "Mumbai", "Delhi", "Kolkata", "Chennai", "Bengaluru", "Hyderabad",
    "Pune", "Ahmedabad", "Jaipur", "Lucknow", "Patna",
    # Odisha Key Districts & Regional Hubs (Sections 5, 6, 9, 14)
    "Bhubaneswar", "Cuttack", "Ganjam", "Puri", "Balasore", "Mayurbhanj",
    "Sambalpur", "Kalahandi", "Koraput", "Bhadrak", "Kendrapara", "Angul", "Sundargarh",
    # Key State Capitals & Mountain/Coastal Hubs
    "Guwahati", "Bhopal", "Chandigarh", "Shimla", "Dehradun", "Srinagar",
    "Thiruvananthapuram", "Kochi", "Visakhapatnam", "Nagpur", "Varanasi",
    "Ranchi", "Imphal", "Shillong", "Agartala", "Kohima", "Itanagar",
    "Gangtok", "Aizawl", "Leh", "Port Blair",
    # All 28 States and 8 Union Territories as Regions (Sections 6, 11)
    "Odisha", "Kerala", "Assam", "West Bengal", "Gujarat", "Rajasthan",
    "Maharashtra", "Tamil Nadu", "Telangana", "Andhra Pradesh",
    "Uttar Pradesh", "Madhya Pradesh", "Bihar", "Jharkhand", "Chhattisgarh",
    "Punjab", "Haryana", "Uttarakhand", "Himachal Pradesh",
    "Jammu & Kashmir", "Ladakh", "Nagaland", "Manipur", "Meghalaya",
    "Mizoram", "Tripura", "Arunachal Pradesh", "Sikkim", "Goa",
    "Andaman & Nicobar Islands", "Chandigarh", "Dadra & Nagar Haveli and Daman & Diu",
    "Delhi", "Lakshadweep", "Puducherry",
]

# ---------------------------------------------------------------------------
# Cyclone-Prone Coastal Districts
# ---------------------------------------------------------------------------

CYCLONE_PRONE_DISTRICTS: List[str] = [
    "Puri", "Kendrapara", "Balasore", "Ganjam", "Jagatsinghpur",
    "Bhadrak", "Vizianagaram", "Visakhapatnam", "Nellore", "Srikakulam",
    "Chennai", "Cuddalore", "Nagapattinam", "Ramanathapuram", "Kanyakumari",
    "Thiruvananthapuram", "Alappuzha", "Kannur", "Kozhikode",
    "Ratnagiri", "Sindhudurg", "Mumbai", "Thane", "Raigad",
    "Surat", "Kutch", "Jamnagar", "Porbandar", "Veraval",
    "Sundarbans", "Midnapore", "South 24 Parganas",
    "Port Blair",
]

# ---------------------------------------------------------------------------
# Flood-Prone Districts
# ---------------------------------------------------------------------------

FLOOD_PRONE_DISTRICTS: List[str] = [
    "Patna", "Darbhanga", "Muzaffarpur", "Saharsa", "Purnia", "Bhagalpur",
    "Guwahati", "Dibrugarh", "Jorhat", "Barpeta", "Nagaon", "Bongaigaon",
    "Varanasi", "Prayagraj", "Gorakhpur", "Ballia", "Ghazipur",
    "Kolkata", "Howrah", "Jalpaiguri", "Murshidabad", "Malda",
    "Mumbai", "Thane", "Raigad", "Nashik", "Kolhapur",
    "Warangal", "Khammam", "Kurnool",
    "Cooch Behar", "Jalpaiguri",
    "Imphal", "Silchar",
]


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def get_state_names() -> List[str]:
    """Return all canonical state/UT display names."""
    return [v["name"] for v in INDIA_STATES.values()]


def get_district_names() -> List[str]:
    """Return all district display names."""
    return [d["district"] for d in INDIA_DISTRICTS]


def get_all_location_names() -> List[str]:
    """Return deduplicated union of all state + district names."""
    seen: set = set()
    result: List[str] = []
    for name in get_state_names() + get_district_names():
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result


def lookup_location(name: str) -> Optional[Dict]:
    """
    Look up lat/lon for a location name (case-insensitive).
    Returns dict with {city, district, state, lat, lon} or None.
    Supports city-to-district resolution (e.g. Bhubaneswar -> Khordha -> Odisha,
    Kochi -> Ernakulam -> Kerala).
    """
    if not name:
        return None
    key = name.strip().lower()
    
    # Try exact city match first (e.g. Bhubaneswar -> Khordha)
    for d in INDIA_DISTRICTS:
        if d.get("city") and d["city"].lower() == key:
            return {
                "city": d["city"],
                "district": d["district"],
                "state": d["state"],
                "lat": d["lat"],
                "lon": d["lon"],
            }
            
    # Try district match
    for d in INDIA_DISTRICTS:
        if d["district"].lower() == key:
            return {
                "city": d.get("city"),
                "district": d["district"],
                "state": d["state"],
                "lat": d["lat"],
                "lon": d["lon"],
            }
            
    # Try comma-separated parts (e.g. "Puri, Odisha")
    if "," in key:
        for part in key.split(","):
            p_res = lookup_location(part.strip())
            if p_res:
                return p_res

    # Try state capitals / state entries
    for sk, sv in INDIA_STATES.items():
        if sv["capital"].lower() == key:
            return {"city": sv["capital"], "district": sv["capital"], "state": sv["name"], "lat": sv["lat"], "lon": sv["lon"]}
        if sv["name"].lower() == key:
            return {"city": None, "district": None, "state": sv["name"], "lat": sv["lat"], "lon": sv["lon"]}

    # Try substring match in compound text
    for d in INDIA_DISTRICTS:
        if d.get("city") and re.search(r'\b' + re.escape(d["city"].lower()) + r'\b', key):
            return {
                "city": d["city"],
                "district": d["district"],
                "state": d["state"],
                "lat": d["lat"],
                "lon": d["lon"],
            }
        if re.search(r'\b' + re.escape(d["district"].lower()) + r'\b', key):
            return {
                "city": d.get("city"),
                "district": d["district"],
                "state": d["state"],
                "lat": d["lat"],
                "lon": d["lon"],
            }

    for sk, sv in INDIA_STATES.items():
        if re.search(r'\b' + re.escape(sv["name"].lower()) + r'\b', key):
            return {"city": None, "district": None, "state": sv["name"], "lat": sv["lat"], "lon": sv["lon"]}

    return None


def get_state_for_district(district: str) -> Optional[str]:
    """Return canonical state name for a given district (case-insensitive)."""
    key = district.strip().lower()
    for d in INDIA_DISTRICTS:
        if (d.get("city") and d["city"].lower() == key) or d["district"].lower() == key:
            return d["state"]
    return None


def validate_location(
    name: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Validates a location without fabricating coordinates.
    If ambiguous:
        coordinates = null
        location_status = AMBIGUOUS
    If verified:
        coordinates = {lat, lon} (only if authentic GPS coordinates exist)
        location_status = VERIFIED
    """
    if name:
        loc = lookup_location(name)
        if loc:
            # Provenance rule: do not fabricate GPS coords from text alone
            has_explicit_gps = (lat is not None and lon is not None and 6.5 <= lat <= 37.6 and 68.0 <= lon <= 97.5)
            coords = {"lat": float(lat), "lon": float(lon)} if has_explicit_gps else None
            return {
                "city": loc.get("city"),
                "district": loc.get("district"),
                "state": loc.get("state"),
                "coordinates": coords,
                "location_status": "VERIFIED",
            }

    return {
        "city": None,
        "district": None,
        "state": None,
        "coordinates": None,
        "location_status": "AMBIGUOUS",
    }


# ---------------------------------------------------------------------------
# State & UT Authoritative Centroid Coordinates
# ---------------------------------------------------------------------------

STATE_CENTROIDS: Dict[str, Tuple[float, float]] = {
    sv["name"]: (sv["lat"], sv["lon"]) for sv in INDIA_STATES.values()
}
# Normalize aliases
STATE_CENTROIDS["Orissa"] = (20.9517, 85.0985)
STATE_CENTROIDS["Pondicherry"] = (11.9416, 79.8083)


# ---------------------------------------------------------------------------
# Deterministic Article Location Extractor (Requirements 5, 6, 7, 8, 9, 10)
# ---------------------------------------------------------------------------

_SPELLING_ALIASES = {
    "orissa": "Odisha",
    "bhubaneshwar": "Bhubaneswar",
    "khurda": "Khordha",
    "baleswar": "Balasore",
    "keonjhar": "Kendujhar",
    "debagarh": "Deogarh",
    "sonepur": "Subarnapur",
    "nawarangpur": "Nabarangpur",
    "bolanir": "Balangir",
    "bangalore": "Bengaluru",
    "baroda": "Vadodara",
    "cochin": "Kochi",
    "trivandrum": "Thiruvananthapuram",
    "gauhati": "Guwahati",
    "calcutta": "Kolkata",
    "madras": "Chennai",
    "bombay": "Mumbai",
    "poona": "Pune",
    "pondicherry": "Puducherry",
}


def resolve_article_locations(
    title: str = "",
    text: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Deterministic Location Resolution Engine (Requirements 5, 6, 7, 8, 9, 10).
    Resolves real Indian geography across 28 states, 8 UTs, and their districts.
    
    CRITICAL RULE (Section 5):
    NEVER default an unknown Odisha article to Bhubaneswar or Puri.
    If the article only says "Odisha", store: state="Odisha", district=None.
    If the article says "14 districts of Odisha", store affected_district_count=14.
    """
    combined_text = f"{title}. {text}".strip()
    clean_lower = combined_text.lower()
    meta = metadata or {}

    # 1. First: Check explicit query/source metadata if passed
    meta_state = meta.get("state") or meta.get("query_state")
    meta_dist = meta.get("district") or meta.get("query_location")

    # 2. Multi-district pattern detection: e.g. "14 districts of Odisha", "7 districts in Kerala"
    multi_dist_match = re.search(r"\b(\d+)\s+districts(?:\s+(?:in|of|across)\s+([A-Za-z\s]+))?", combined_text, re.IGNORECASE)
    multi_count = int(multi_dist_match.group(1)) if multi_dist_match else 0
    multi_state_hint = multi_dist_match.group(2).strip() if (multi_dist_match and multi_dist_match.group(2)) else None

    # 3. Detect all mentioned districts and states across the entire text
    matched_districts: List[Dict[str, Any]] = []
    matched_states: Set[str] = set()

    # Apply spelling alias replacements for token matching
    for alias_src, canonical in _SPELLING_ALIASES.items():
        if re.search(r"\b" + re.escape(alias_src) + r"\b", clean_lower):
            # If alias is a state
            if canonical in STATE_CENTROIDS:
                matched_states.add(canonical)

    # Check all registered districts (longest match first)
    sorted_districts = sorted(INDIA_DISTRICTS, key=lambda d: len(d["district"]), reverse=True)
    for d in sorted_districts:
        d_name = d["district"].lower()
        c_name = d.get("city", "").lower() if d.get("city") else None

        # Check district name word boundary
        if re.search(r"\b" + re.escape(d_name) + r"\b", clean_lower):
            if not any(md["district"].lower() == d_name for md in matched_districts):
                matched_districts.append(d)
                matched_states.add(d["state"])

        # Check city name word boundary
        elif c_name and re.search(r"\b" + re.escape(c_name) + r"\b", clean_lower):
            if not any(md.get("city", "").lower() == c_name for md in matched_districts):
                matched_districts.append(d)
                matched_states.add(d["state"])

    # Check all registered states
    for sk, sv in INDIA_STATES.items():
        st_name = sv["name"]
        if re.search(r"\b" + re.escape(st_name.lower()) + r"\b", clean_lower):
            matched_states.add(st_name)

    if multi_state_hint:
        for sk, sv in INDIA_STATES.items():
            if sv["name"].lower() in multi_state_hint.lower():
                matched_states.add(sv["name"])

    # Fallback to metadata state/district if text gave nothing
    if not matched_states and meta_state:
        for sk, sv in INDIA_STATES.items():
            if sv["name"].lower() == meta_state.lower() or sk == meta_state.lower():
                matched_states.add(sv["name"])

    # 4. Resolve Primary vs Multi-Location
    primary_state: Optional[str] = None
    primary_district: Optional[str] = None
    primary_city: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    resolution_method = "UNRESOLVED"
    resolution_confidence = 0.0

    affected_districts = [d["district"] for d in matched_districts]
    affected_states = list(matched_states)

    if len(matched_districts) == 1:
        # Exact Single District / City match
        top_d = matched_districts[0]
        primary_district = top_d["district"]
        primary_city = top_d.get("city")
        primary_state = top_d["state"]
        lat = top_d["lat"]
        lon = top_d["lon"]
        resolution_method = "CITY_MATCH" if primary_city else "DISTRICT_MATCH"
        resolution_confidence = 0.95

    elif len(matched_districts) > 1:
        # Multi-district article (Section 8: e.g. "Rain warning for Ganjam, Puri and Cuttack")
        # Primary is the first mentioned district or highest severity
        first_d = matched_districts[0]
        primary_district = first_d["district"]
        primary_city = first_d.get("city")
        primary_state = first_d["state"]
        lat = first_d["lat"]
        lon = first_d["lon"]
        resolution_method = "MULTI_DISTRICT"
        resolution_confidence = 0.90
        if multi_count == 0:
            multi_count = len(matched_districts)

    elif matched_states:
        # State-level article (Section 10: article only contains "Odisha" without specific district)
        # NEVER assign Bhubaneswar or Puri! (Section 5)
        primary_state = list(matched_states)[0]
        primary_district = None
        primary_city = None
        # State-level centroid representation (Section 22)
        if primary_state in STATE_CENTROIDS:
            lat, lon = STATE_CENTROIDS[primary_state]
        resolution_method = "MULTI_DISTRICT" if multi_count > 0 else "STATE_LEVEL"
        resolution_confidence = 0.80

    return {
        "country": "IN",
        "primary_state": primary_state,
        "primary_district": primary_district,
        "primary_city": primary_city,
        "affected_states": affected_states,
        "affected_districts": affected_districts,
        "affected_district_count": max(multi_count, len(affected_districts)),
        "latitude": lat,
        "longitude": lon,
        "resolution_method": resolution_method,
        "resolution_confidence": resolution_confidence,
    }


