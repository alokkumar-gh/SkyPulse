"""
SkyPulse Multilingual Weather Keyword Engine
=============================================
Weather event keywords in 11 Indian languages + English, used to build
discovery search queries across Google News RSS, regional news RSS,
and public alert feeds.

Languages
---------
  en  – English
  hi  – Hindi (Devanagari)
  or  – Odia
  bn  – Bengali
  mr  – Marathi
  gu  – Gujarati
  ta  – Tamil
  te  – Telugu
  kn  – Kannada
  ml  – Malayalam
  pa  – Punjabi (Gurmukhi)
  as  – Assamese

Weather Event Categories (aligned with WeatherCategory enum)
------------------------------------------------------------
  HEAVY_RAIN     | CYCLONE       | FLOOD         | HEATWAVE
  THUNDERSTORM   | FOG           | DUST_STORM    | COLD_WAVE
  LANDSLIDE      | CLOUDBURST    | STRONG_WINDS  | ALERT_GENERAL
"""

from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
LangCode = str   # ISO 639-1 / local code
EventKey = str   # matches WeatherCategory slug


# ---------------------------------------------------------------------------
# Master keyword dictionary
# Format: KEYWORDS[event_key][lang_code] = [keyword1, keyword2, ...]
# ---------------------------------------------------------------------------

KEYWORDS: Dict[EventKey, Dict[LangCode, List[str]]] = {

    "HEAVY_RAIN": {
        "en": ["heavy rain", "heavy rainfall", "torrential rain", "downpour", "incessant rain",
                "extremely heavy rain", "very heavy rain", "red alert rain", "orange alert rain"],
        "hi": ["भारी बारिश", "अत्यधिक वर्षा", "मूसलाधार बारिश", "भारी वर्षा", "बाढ़ की बारिश",
                "भारी बरसात", "तेज बारिश"],
        "or": ["ଭାରି ବର୍ଷା", "ଅତ୍ୟଧିକ ବର୍ଷା", "ଝୋଡ଼ ବର୍ଷା", "ଭାରି ବୃଷ୍ଟି"],
        "bn": ["ভারী বৃষ্টি", "প্রবল বৃষ্টিপাত", "মুষলধারে বৃষ্টি", "অতি ভারী বর্ষণ", "ভারী বর্ষা"],
        "mr": ["मुसळधार पाऊस", "जड पाऊस", "अतिवृष्टी", "धुवाधार पाऊस", "भारी पाऊस"],
        "gu": ["ભારે વરસાદ", "ધોધમાર વરસાદ", "ઘણો વરસાદ", "ભારી વરસા"],
        "ta": ["கனமழை", "பலத்த மழை", "மிகவும் கனமழை", "கடும் மழை", "கன மழைப் பொழிவு"],
        "te": ["భారీ వర్షాలు", "అతిభారీ వర్షం", "కుంభవృష్టి", "భారీ వర్షపాతం"],
        "kn": ["ಭಾರೀ ಮಳೆ", "ಅತಿ ಭಾರೀ ಮಳೆ", "ದಿಢೀರ್ ಮಳೆ", "ಜೋರಾದ ಮಳೆ"],
        "ml": ["ശക്തമായ മഴ", "കനത്ത മഴ", "അതിതീവ്ര മഴ", "ഭാരിച്ച മഴ"],
        "pa": ["ਭਾਰੀ ਬਾਰਸ਼", "ਮੂਸਲਾਧਾਰ ਮੀਂਹ", "ਭਾਰੀ ਵਰਖਾ"],
        "as": ["ভাৰী বৰষুণ", "প্ৰচণ্ড বৰষুণ", "মুষলধাৰে বৰষুণ"],
    },

    "CYCLONE": {
        "en": ["cyclone", "cyclonic storm", "severe cyclone", "very severe cyclone",
                "super cyclone", "cyclone warning", "IMD cyclone alert", "tropical storm",
                "depression", "deep depression", "low pressure cyclone"],
        "hi": ["चक्रवात", "चक्रवाती तूफान", "चक्रवात चेतावनी", "भीषण चक्रवात", "उष्णकटिबंधीय तूफान"],
        "or": ["ଘୂର୍ଣ୍ଣିବାତ", "ସାଇକ୍ଲୋନ", "ଘୂର୍ଣ୍ଣିଝଡ଼", "ବାତ୍ୟା", "ଘୂର୍ଣ୍ଣି ଚେତାବନୀ"],
        "bn": ["ঘূর্ণিঝড়", "সাইক্লোন", "ঘূর্ণিঝড় সতর্কতা", "ক্রান্তীয় ঝড়"],
        "mr": ["चक्रीवादळ", "वादळ इशारा", "उष्णकटिबंधीय चक्रीवादळ"],
        "gu": ["વાવાઝોડું", "ચક્રવાત", "ચક્રવાત ચેતવણી", "ઉષ્ણકટિબંધીય તોફાન"],
        "ta": ["சுழற்காற்று", "புயல்", "புயல் எச்சரிக்கை", "வெப்ப மண்டல புயல்"],
        "te": ["తుఫాను", "సైక్లోన్", "తుఫాను హెచ్చరిక", "ఉష్ణమండల తుఫాను"],
        "kn": ["ಚಂಡಮಾರುತ", "ಚಕ್ರವಾತ", "ಬಿರುಗಾಳಿ ಎಚ್ಚರಿಕೆ"],
        "ml": ["ചുഴലിക്കാറ്റ്", "ഉഷ്ണമേഖലാ ചുഴലിക്കാറ്റ്", "ചുഴലി മുന്നറിയിപ്പ്"],
        "pa": ["ਚੱਕਰਵਾਤ", "ਤੂਫ਼ਾਨ", "ਚੱਕਰਵਾਤ ਚੇਤਾਵਨੀ"],
        "as": ["ঘূৰ্ণীবতাহ", "ঘূৰ্ণীঝড়", "ঘূৰ্ণীবতাহ সতৰ্কতা"],
    },

    "FLOOD": {
        "en": ["flood", "flooding", "flash flood", "waterlogging", "inundation",
                "river flood", "urban flood", "flood warning", "dam overflow", "embankment breach"],
        "hi": ["बाढ़", "बाढ़ की चेतावनी", "जलभराव", "नदी में बाढ़", "अचानक बाढ़", "बांध टूटना"],
        "or": ["ବନ୍ୟା", "ବାଢ଼ ଚେତାବନୀ", "ଜଳ ପ୍ଳାବନ", "ଫ୍ଲାଶ ଫ୍ଲଡ", "ବନ୍ୟା ଆଶଙ୍କା"],
        "bn": ["বন্যা", "বন্যার সতর্কতা", "জলাবদ্ধতা", "আকস্মিক বন্যা", "প্লাবন"],
        "mr": ["पूर", "पूर इशारा", "जलमय", "महापूर", "अचानक पूर"],
        "gu": ["પૂর", "પૂรนો ખtara", "ઘs", "ઘoળo"],
        "ta": ["வெள்ளம்", "வெள்ளப் பெருக்கு", "வெள்ள எச்சரிக்கை", "நகர்ப்புற வெள்ளம்"],
        "te": ["వరదలు", "వరద హెచ్చరిక", "నగర వరదలు", "అకస్మాత్తు వరదలు"],
        "kn": ["ಪ್ರವಾಹ", "ನೆರೆ", "ಪ್ರವಾಹ ಎಚ್ಚರಿಕೆ", "ನಗರ ಪ್ರವಾಹ"],
        "ml": ["വെള്ളപ്പൊക്കം", "ഉൾപ്രദേശ വെള്ളപ്പൊക്കം", "വെള്ളപ്പൊക്ക മുന്നറിയിപ്പ്"],
        "pa": ["ਹੜ੍ਹ", "ਹੜ੍ਹ ਦੀ ਚੇਤਾਵਨੀ", "ਜਲ ਭਰਾਅ"],
        "as": ["বান পানী", "বানপানী সতৰ্কতা", "উপচি পৰা"],
    },

    "HEATWAVE": {
        "en": ["heatwave", "heat wave", "severe heatwave", "extreme heat", "heat alert",
                "heat stroke", "high temperature warning", "scorching heat", "heat action plan"],
        "hi": ["लू", "गर्मी की लहर", "भीषण गर्मी", "ताप लहर", "लू चेतावनी", "गर्म हवा"],
        "or": ["ଉତ୍ତାପ ତରଙ୍ଗ", "ତୀବ୍ର ଗ୍ରୀଷ୍ମ", "ଲୁ", "ଗ୍ରୀଷ୍ମ ଲହର"],
        "bn": ["তাপপ্রবাহ", "দাবদাহ", "তীব্র গরম", "তাপঢেউ"],
        "mr": ["उष्माघात", "उष्ण लाट", "तीव्र उष्णता", "उष्णतेची लाट"],
        "gu": ["ગરમી", "ઉષ્ણ ld", "loo", "loo chetnī", "lic heat"],
        "ta": ["வெப்ப அலை", "கடுமையான வெயில்", "வெப்ப எச்சரிக்கை"],
        "te": ["వేడి గాలులు", "వడగాల్పులు", "వేడి అలలు", "వేడి హెచ్చరిక"],
        "kn": ["ಶಾಖದ ಅಲೆ", "ತೀವ್ರ ಬಿಸಿಲು", "ಉಷ್ಣ ಅಲೆ"],
        "ml": ["ചൂടുതരംഗം", "തിളക്കമുള്ള വെയിൽ", "ഉഷ്ണ തരംഗം"],
        "pa": ["ਗਰਮੀ ਦੀ ਲਹਿਰ", "ਲੂ", "ਭਿਆਨਕ ਗਰਮੀ"],
        "as": ["তাপ প্ৰবাহ", "তীব্ৰ গৰম", "লু বতাহ"],
    },

    "THUNDERSTORM": {
        "en": ["thunderstorm", "lightning", "thunder", "severe thunderstorm",
                "electrical storm", "lightning strike", "squall", "storm warning"],
        "hi": ["आंधी", "तूफान", "बिजली गिरना", "गरज के साथ बारिश", "वज्रपात", "आंधी-तूफान"],
        "or": ["ଗର୍ଜନ", "ଝଡ", "ବଜ୍ରପାତ", "ଗର୍ଜନ-ସହ-ବର୍ଷା", "ଝଡ ଚେତାବନୀ"],
        "bn": ["বজ্রঝড়", "বজ্রপাত", "ঘূর্ণিঝড়", "বিদ্যুৎ পড়া", "ঝড় সতর্কতা"],
        "mr": ["विजांचा कडकडाट", "वादळ", "गडगडाट", "विजेचा कडाडा"],
        "gu": ["ગurjr", "vc", "vij", "tot"],
        "ta": ["இடிமுழக்கம்", "மின்னல்", "புயல்", "கொடுங்காற்று"],
        "te": ["ఉరుములు", "మెరుపులు", "గాలివాన", "తుఫాను హెచ్చరిక"],
        "kn": ["ಗುಡುಗು", "ಮಿಂಚು", "ಬಿರುಗಾಳಿ", "ಗಾಳಿ ಮಳೆ"],
        "ml": ["ഇടിമുഴക്കം", "മിന്നൽ", "കൊടുങ്കാറ്റ്"],
        "pa": ["ਤੂਫ਼ਾਨ", "ਬਿਜਲੀ", "ਗਰਜ ਵਾਲਾ ਤੂਫ਼ਾਨ"],
        "as": ["বজ্ৰপাত", "ঘন ঘন বজ্ৰপাত", "বজ্ৰবিদ্যুৎ"],
    },

    "FOG": {
        "en": ["fog", "dense fog", "severe fog", "low visibility", "foggy conditions",
                "fog warning", "visibility reduced", "smog"],
        "hi": ["कोहरा", "घना कोहरा", "धुंध", "कोहरा चेतावनी", "कम दृश्यता"],
        "or": ["କୁହୁଡ଼ି", "ଘଞ୍ଚ କୁହୁଡ଼ି", "ମହୁ"],
        "bn": ["কুয়াশা", "ঘন কুয়াশা", "কুয়াশা সতর্কতা"],
        "mr": ["धुके", "दाट धुके", "धुक्याची सूचना"],
        "gu": ["靴", "dhūm", "paṭlu dhūm"],
        "ta": ["மூடுபனி", "அடர்ந்த மூடுபனி"],
        "te": ["పొగమంచు", "దట్టమైన పొగమంచు"],
        "kn": ["ಮಂಜು", "ದಟ್ಟ ಮಂಜು"],
        "ml": ["മഞ്ഞ്", "ഇടതൂർന്ന മഞ്ഞ്"],
        "pa": ["ਧੁੰਦ", "ਸੰਘਣੀ ਧੁੰਦ"],
        "as": ["কুঁৱলী", "গধুৰ কুঁৱলী"],
    },

    "DUST_STORM": {
        "en": ["dust storm", "sandstorm", "dust devil", "visibility near zero",
                "haboob", "sand squall", "dust warning"],
        "hi": ["आंधी", "धूल भरी आंधी", "रेत का तूफान", "धूल तूफान"],
        "or": ["ଧୂଳି ଝଡ", "ବালୁ ଝଡ"],
        "bn": ["ধূলিঝড়", "বালি ঝড়", "বালিঝড়"],
        "mr": ["धुळीचे वादळ", "वाळूचे वादळ"],
        "gu": ["rētīvāvaÇolum", "dhūḷibharyā pavasanī"],
        "ta": ["மணல் புயல்", "தூசி புயல்"],
        "te": ["ఇసుక తుఫాను", "ధూళి తుఫాను"],
        "kn": ["ಮರಳು ಬಿರುಗಾಳಿ", "ಧೂಳಿನ ಬಿರುಗಾಳಿ"],
        "ml": ["മണൽ കൊടുങ്കാറ്റ്", "പൊടി കൊടുങ്കാറ്റ്"],
        "pa": ["ਰੇਤ ਦਾ ਤੂਫ਼ਾਨ", "ਧੂੜ ਦਾ ਤੂਫ਼ਾਨ"],
        "as": ["বালিবতাহ", "ধূলিবতাহ"],
    },

    "COLD_WAVE": {
        "en": ["cold wave", "cold spell", "severe cold", "winter alert",
                "freezing conditions", "frost", "sub-zero temperature", "icy conditions"],
        "hi": ["शीत लहर", "ठंड की लहर", "कड़ाके की ठंड", "पाला", "शीत लहर चेतावनी"],
        "or": ["ଶୀତ ଲହର", "ଭୀଷଣ ଶୀତ", "ଶୀତ ଚେତାବନୀ"],
        "bn": ["শীতলহর", "তীব্র শীত", "শীত সতর্কতা", "হিমানী"],
        "mr": ["थंडीची लाट", "कडाक्याची थंडी", "शीत लाट"],
        "gu": ["ठंडी", "ठंडी लहर", "ઠàÃîdar"],
        "ta": ["குளிர்அலை", "தீவிர குளிர்"],
        "te": ["శీతల అలలు", "తీవ్ర చలి"],
        "kn": ["ಶೀತ ಅಲೆ", "ತೀವ್ರ ಚಳಿ"],
        "ml": ["ശൈത്യ തരംഗം", "കൊടും ശൈത്യം"],
        "pa": ["ਠੰਡ ਦੀ ਲਹਿਰ", "ਕੜਾਕੇ ਦੀ ਠੰਡ"],
        "as": ["শীত প্ৰবাহ", "তীব্ৰ শীত"],
    },

    "LANDSLIDE": {
        "en": ["landslide", "mudslide", "rockslide", "debris flow", "slope failure",
                "landslip", "land collapse"],
        "hi": ["भूस्खलन", "पहाड़ टूटना", "मिट्टी खिसकना", "चट्टान खिसकना"],
        "or": ["ଭୂସ୍ଖଳନ", "ମୃତ୍ତିକା ସ୍ଖଳନ"],
        "bn": ["ভূমিধস", "মাটি ধস", "পাহাড় ধস"],
        "mr": ["दरड कोसळणे", "भूस्खलन", "मातीचा ढिगारा"],
        "gu": ["ભૂskhalan", "bhūml padi"],
        "ta": ["நிலச்சரிவு", "மண்சரிவு"],
        "te": ["కొండ చరియలు", "భూపతనం"],
        "kn": ["ಭೂಕುಸಿತ", "ಮಣ್ಣುಕುಸಿತ"],
        "ml": ["ഉരുൾ പൊട്ടൽ", "മലയിടിച്ചിൽ"],
        "pa": ["ਭੂ-ਖਿਸਕਣ", "ਪਹਾੜੀ ਖਿਸਕਣ"],
        "as": ["ভূমিস্খলন", "পাহাৰ ভাঙি পড়া"],
    },

    "CLOUDBURST": {
        "en": ["cloudburst", "cloudbursts", "sudden heavy downpour", "extreme rainfall event",
                "micro-burst", "300mm rain"],
        "hi": ["बादल फटना", "बादल फटने", "अचानक भारी बारिश"],
        "or": ["ମେଘ ବିସ୍ଫୋଟ", "ମେଘ ଫଟା"],
        "bn": ["মেঘভাঙা বৃষ্টি", "মেঘ ফাটা"],
        "mr": ["ढग फुटणे", "अचानक मुसळधार पाऊस"],
        "gu": ["vaādaḷ phūṭavum", "ākasmat bhārī varāsad"],
        "ta": ["மேகவெடிப்பு", "திடீர் கனமழை"],
        "te": ["మేఘం పేలుడు", "అకస్మాత్తు భారీ వర్షం"],
        "kn": ["ಮೋಡ ಸ್ಫೋಟ", "ಹಠಾತ್ ಭಾರೀ ಮಳೆ"],
        "ml": ["മേഘസ്ഫോടനം", "പെട്ടെന്നുള്ള ശക്തമായ മഴ"],
        "pa": ["ਬੱਦਲ ਫਟਣਾ"],
        "as": ["মেঘ ফাটি পৰা"],
    },

    "STRONG_WINDS": {
        "en": ["strong winds", "gale force winds", "squall", "high wind warning",
                "wind speed", "gusts", "storm force wind"],
        "hi": ["तेज हवाएं", "आंधी", "तूफानी हवाएं", "झक्खड़"],
        "or": ["ପ୍ରବଳ ବায়ୁ", "ଝଡ଼ ବାୟୁ"],
        "bn": ["প্রবল বাতাস", "ঝড়ো হাওয়া"],
        "mr": ["वेगाचे वारे", "वादळी वारे"],
        "gu": ["tīvra vāyu", "pavan vāyro"],
        "ta": ["கடும் காற்று", "புயல் காற்று"],
        "te": ["తీవ్రమైన గాలులు", "తుఫాను గాలులు"],
        "kn": ["ತೀವ್ರ ಗಾಳಿ", "ಝಂಝಾ ಗಾಳಿ"],
        "ml": ["ശക്തമായ കാറ്റ്", "കൊടുങ്കൊടുంകാറ്റ്"],
        "pa": ["ਤੇਜ਼ ਹਵਾਵਾਂ", "ਝੱਖੜ"],
        "as": ["প্ৰচণ্ড বতাহ", "ঝড় বতাহ"],
    },

    "ALERT_GENERAL": {
        "en": ["weather alert", "weather warning", "red alert", "orange alert", "yellow alert",
                "IMD warning", "NDMA alert", "weather advisory", "extreme weather",
                "meteorological warning", "SACHET alert"],
        "hi": ["मौसम चेतावनी", "लाल अलर्ट", "नारंगी अलर्ट", "पीला अलर्ट", "आईएमडी चेतावनी"],
        "or": ["ପାଣିପାଗ ଚେତାବନୀ", "ଲାଲ ଆଲର୍ଟ", "ଆଇଏମଡି ଚେତାବନୀ"],
        "bn": ["আবহাওয়া সতর্কতা", "লাল সতর্কতা", "IMD সতর্কতা"],
        "mr": ["हवामान इशारा", "लाल इशारा", "IMD इशारा"],
        "gu": ["havāman cetavṇī", "lāl alerṭ"],
        "ta": ["வானிலை எச்சரிக்கை", "சிவப்பு எச்சரிக்கை"],
        "te": ["వాతావరణ హెచ్చరిక", "ఎర్ర హెచ్చరిక"],
        "kn": ["ಹವಾಮಾನ ಎಚ್ಚರಿಕೆ", "ಕೆಂಪು ಎಚ್ಚರಿಕೆ"],
        "ml": ["കാലാവസ്ഥ മുന്നറിയിപ്പ്", "ചുവന്ന ജാഗ്രതാ"],
        "pa": ["ਮੌਸਮ ਚੇਤਾਵਨੀ", "ਲਾਲ ਚੇਤਾਵਨੀ"],
        "as": ["বতৰ সতৰ্কতা", "ৰঙা সতৰ্কতা"],
    },
}

# ---------------------------------------------------------------------------
# Language metadata
# ---------------------------------------------------------------------------

LANGUAGE_META: Dict[LangCode, Dict] = {
    "en": {"name": "English",   "script": "Latin",      "priority": 1},
    "hi": {"name": "Hindi",     "script": "Devanagari", "priority": 2},
    "or": {"name": "Odia",      "script": "Odia",       "priority": 3},
    "bn": {"name": "Bengali",   "script": "Bengali",    "priority": 3},
    "mr": {"name": "Marathi",   "script": "Devanagari", "priority": 3},
    "gu": {"name": "Gujarati",  "script": "Gujarati",   "priority": 4},
    "ta": {"name": "Tamil",     "script": "Tamil",      "priority": 4},
    "te": {"name": "Telugu",    "script": "Telugu",     "priority": 4},
    "kn": {"name": "Kannada",   "script": "Kannada",    "priority": 4},
    "ml": {"name": "Malayalam", "script": "Malayalam",  "priority": 4},
    "pa": {"name": "Punjabi",   "script": "Gurmukhi",   "priority": 4},
    "as": {"name": "Assamese",  "script": "Bengali",    "priority": 4},
}

# Language → primary states coverage
LANGUAGE_STATE_COVERAGE: Dict[LangCode, List[str]] = {
    "en": [],  # All states
    "hi": ["Uttar Pradesh", "Bihar", "Madhya Pradesh", "Rajasthan", "Jharkhand",
            "Chhattisgarh", "Uttarakhand", "Delhi", "Haryana", "Himachal Pradesh"],
    "or": ["Odisha"],
    "bn": ["West Bengal", "Tripura"],
    "mr": ["Maharashtra", "Goa"],
    "gu": ["Gujarat"],
    "ta": ["Tamil Nadu", "Puducherry"],
    "te": ["Telangana", "Andhra Pradesh"],
    "kn": ["Karnataka"],
    "ml": ["Kerala", "Lakshadweep"],
    "pa": ["Punjab", "Chandigarh", "Haryana"],
    "as": ["Assam", "Arunachal Pradesh", "Nagaland", "Mizoram", "Manipur", "Meghalaya"],
}

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_keywords_for_event(event: EventKey, languages: Optional[List[LangCode]] = None) -> List[str]:
    """
    Return all keyword strings for a given weather event category,
    optionally filtered to specific languages.
    """
    event_kws = KEYWORDS.get(event, {})
    result: List[str] = []
    for lang, kws in event_kws.items():
        if languages is None or lang in languages:
            result.extend(kws)
    return result


def get_all_event_keys() -> List[EventKey]:
    """Return all event category keys."""
    return list(KEYWORDS.keys())


def get_languages_for_state(state: str) -> List[LangCode]:
    """
    Return recommended languages to use when querying for a given Indian state.
    Always includes English (en).
    """
    result: List[LangCode] = ["en"]
    for lang, states in LANGUAGE_STATE_COVERAGE.items():
        if not states or state in states:
            if lang != "en" and lang not in result:
                result.append(lang)
    # Always return at most 4 for query efficiency (en + top 3 local)
    return result[:4]


def get_high_priority_keywords(max_per_event: int = 3) -> Dict[EventKey, List[str]]:
    """
    Return a compact subset of English-only keywords for high-frequency polling.
    """
    result: Dict[EventKey, List[str]] = {}
    for event, lang_kws in KEYWORDS.items():
        en_kws = lang_kws.get("en", [])
        result[event] = en_kws[:max_per_event]
    return result
