from flask import Flask, request, jsonify, render_template, send_file
import re
import speech_recognition as sr
from gtts import gTTS
import os
import uuid
import difflib
import math

app = Flask(__name__)

# Structured campus data with coordinates
campus_data = {
    "gate": {"lat": 17.05973, "lng": 81.86922, "description": "Main campus entrance"},
    "globe": {"lat": 17.05997, "lng": 81.86928, "description": "Globe monument near entrance"},
    "main block parking": {"lat": 17.05957, "lng": 81.86877, "description": "Parking near main block"},
    "parking 2": {"lat": 17.06213, "lng": 81.86849, "aliases": ["fc"], "description": "Parking near food court"},
    "atm": {"lat": 17.06000, "lng": 81.86913, "description": "ATM machine location"},
    "main block": {"lat": 17.05975, "lng": 81.86875, "description": "Main academic building"},
    "saraswati devi": {"lat": 17.06026, "lng": 81.86875, "description": "Saraswati Devi statue"},
    "amphitheatre": {"lat": 17.06055, "lng": 81.86902, "description": "Open-air amphitheater"},
    "vishwesaraya block": {"lat": 17.06089, "lng": 81.86833, "description": "Engineering department building"},
    "juice shop": {"lat": 17.06146, "lng": 81.86780, "description": "Juice and snack bar"},
    "food stalls": {"lat": 17.06141, "lng": 81.86795, "description": "Street food vendors"},
    "food court": {"lat": 17.06148, "lng": 81.86780, "description": "Main food court area"},
    "mechanical labs": {"lat": 17.06434, "lng": 81.86737, "description": "Mechanical engineering laboratories"},
    "boys mess": {"lat": 17.06179, "lng": 81.86716, "description": "Boys hostel dining hall"},
    "girls hostel": {"lat": 17.06202, "lng": 81.86674, "description": "Girls accommodation block"},
    "basketball court": {"lat": 17.06213, "lng": 81.86769, "description": "Basketball playing area"},
    "football court": {"lat": 17.06259, "lng": 81.86766, "description": "Football/soccer field"},
    "mining block": {"lat": 17.06284, "lng": 81.86721, "description": "Mining engineering department"},
    "bamboos": {"lat": 17.06223, "lng": 81.86861, "description": "Bamboo garden area"},
    "yummpys": {"lat": 17.06323, "lng": 81.86791, "aliases": ["yummy"], "description": "Yummpy's snack shop"},
    "boys hostel": {"lat": 17.06313, "lng": 81.86563, "description": "Boys accommodation block"},
    "saibaba temple": {"lat": 17.06331, "lng": 81.86706, "description": "Saibaba temple on campus"},
    "pharmacy block": {"lat": 17.06360, "lng": 81.86576, "description": "Pharmacy department building"},
    "library": {"lat": 17.06410, "lng": 81.86618, "description": "Main campus library", "hours": "8AM-10PM"},
    "rk block": {"lat": 17.06426, "lng": 81.86590, "description": "RK academic block"},
    "central food court": {"lat": 17.06459, "lng": 81.86744, "aliases": ["cfc"], "description": "Central dining area"},
    "diploma block": {"lat": 17.06513, "lng": 81.86574, "description": "Diploma studies building"},
    "international boys hostel": {"lat": 17.06584, "lng": 81.86564, "description": "Hostel for international students"},
    "cricket ground": {"lat": 17.06493, "lng": 81.86880, "description": "Cricket playing field"},
    "bus ground": {"lat": 17.06479, "lng": 81.86598, "description": "Bus parking and pickup area"},
    "automobile engineering lab": {"lat": 17.06449, "lng": 81.86969, "description": "Automotive engineering lab"},
    "lakepond": {"lat": 17.06875, "lng": 81.86769, "description": "Lake and pond area"},
    "cv raman block": {"lat": 17.06846, "lng": 81.86727, "description": "CV Raman science block"},
    "spicehub": {"lat": 17.06896, "lng": 81.86838, "description": "SpiceHub food court"},
    "giet parking 3": {"lat": 17.06936, "lng": 81.86837, "description": "Parking area near SpiceHub"},
    "degree block": {"lat": 17.07090, "lng": 81.86853, "description": "Degree programs building"},
    "events ground": {"lat": 17.07154, "lng": 81.86830, "description": "Events and festival ground"},
    "lake": {"lat": 17.07146, "lng": 81.86981, "description": "Main campus lake"}
}

# Create alias mapping
alias_mapping = {}
for name, data in campus_data.items():
    aliases = data.get("aliases", [])
    for alias in aliases:
        alias_mapping[alias.lower()] = name
    alias_mapping[name.lower()] = name

# Precompute all location names for fuzzy matching
all_location_names = list(campus_data.keys()) + list(alias_mapping.keys())

def find_location(location_str):
    """Find location in database using name or alias with fuzzy matching"""
    if not location_str or location_str.strip() == "":
        return None
        
    location_str = location_str.lower().strip()
    
    # 1. Check direct match
    if location_str in alias_mapping:
        return alias_mapping[location_str]
    
    # 2. Check for similar matches
    matches = [name for name in campus_data.keys() if location_str in name.lower()]
    if matches:
        return matches[0]
    
    # 3. Try partial matches
    for name in campus_data.keys():
        if location_str in name.lower().replace(" ", ""):
            return name
            
    # 4. Fuzzy matching using difflib
    matches = difflib.get_close_matches(location_str, all_location_names, n=1, cutoff=0.5)
    if matches:
        return alias_mapping.get(matches[0].lower(), matches[0])
    
    return None

def calculate_distance(start, end):
    """Calculate approximate straight-line distance in meters"""
    # Convert latitude and longitude differences to meters
    lat_diff = abs(campus_data[start]['lat'] - campus_data[end]['lat']) * 111000
    lng_diff = abs(campus_data[start]['lng'] - campus_data[end]['lng']) * 111000
    return math.sqrt(lat_diff**2 + lng_diff**2)

def generate_directions(start, end):
    """Generate directions message with Google Maps link"""
    start_coords = f"{campus_data[start]['lat']},{campus_data[start]['lng']}"
    end_coords = f"{campus_data[end]['lat']},{campus_data[end]['lng']}"
    
    maps_url = f"https://www.google.com/maps/dir/{start_coords}/{end_coords}"
    distance = calculate_distance(start, end)
    walking_time = distance / 67  # 67 meters per minute
    
    # Generate directions description
    description = (
        f"🚶 Directions from {start.capitalize()} to {end.capitalize()}:\n"
        f"📍 Distance: Approximately {distance:.0f} meters\n"
        f"⏱️ Walking time: {max(1, int(walking_time))} minutes\n"
        f"🗺️ [Open in Google Maps]({maps_url})"
    )
    
    # Add location description if available
    if "description" in campus_data[end]:
        description += f"\n\nℹ️ About this location: {campus_data[end]['description']}"
    
    # Add hours if available
    if "hours" in campus_data[end]:
        description += f"\n🕒 Hours: {campus_data[end]['hours']}"
    
    return description

def process_message(user_message):
    """Process user message and generate response"""
    user_message = user_message.lower()
    response = ""
    
    # Patterns for different types of queries
    from_to_pattern = r'(?:from|between)\s+(.+?)\s+(?:to|and)\s+(.+)'
    to_pattern = r'(?:to|for|towards|near)\s+(.+)'
    where_pattern = r'(?:where\s+is|find|locate|show me|how to get to)\s+(.+)'
    info_pattern = r'(?:info|information|details|about|tell me about)\s+(.+)'
    help_pattern = r'(?:help|what can you do|options|features)'
    map_pattern = r'(?:map|campus map|whole map|complete map)'
    simple_directions_pattern = r'(.+?)\s+to\s+(.+)'
    current_location_pattern = r'(?:where am i|my location|current location)'
    
    start = None
    end = None
    
    try:
        # Check for help request
        if re.search(help_pattern, user_message):
            return (
                "🌟 I'm your campus navigation assistant! I can help with:\n"
                "- Directions between locations (e.g., 'How to go from main block to library')\n"
                "- Finding places (e.g., 'Where is the cafeteria?')\n"
                "- Information about locations (e.g., 'Info about library')\n"
                "- Campus map with all locations\n"
                "You can also use voice commands by clicking the microphone icon!"
            )
        
        # Check for map request
        if re.search(map_pattern, user_message):
            markers = "&markers=" + "|".join([f"{data['lat']},{data['lng']}" for data in campus_data.values()])
            map_url = f"https://www.google.com/maps?{markers}&q=17.05973,81.86922"
            
            return (
                "🗺️ Here's the complete campus map:\n"
                f"📍 [View Campus Map on Google Maps]({map_url})\n\n"
                "Key locations include:\n"
                "- " + "\n- ".join([name.capitalize() for name in list(campus_data.keys())[:10]]) + "\n...and more!"
            )
        
        # Check for location information request
        if info_match := re.search(info_pattern, user_message):
            loc_str = info_match.group(1).strip()
            location = find_location(loc_str)
            
            if location and location in campus_data:
                data = campus_data[location]
                response = f"ℹ️ Information about {location.capitalize()}:\n"
                response += f"- Description: {data['description']}\n"
                if "hours" in data:
                    response += f"- Hours: {data['hours']}\n"
                
                # Find nearby locations
                nearby = []
                for other_name, other_data in campus_data.items():
                    if other_name != location:
                        dist = calculate_distance(location, other_name)
                        if dist < 200:  # within 200 meters
                            nearby.append((other_name, dist))
                
                if nearby:
                    response += "\n📍 Nearby locations:\n"
                    for name, dist in sorted(nearby, key=lambda x: x[1])[:3]:
                        response += f"- {name.capitalize()} ({dist:.0f}m)\n"
            else:
                response = f"❌ Sorry, I couldn't find information about '{loc_str}'. Try asking about specific campus locations."
            return response
        
        # Check for "where am I" request
        if re.search(current_location_pattern, user_message):
            return (
                "📍 I can't determine your exact location, but here's the campus map:\n"
                "🗺️ [View Campus Map on Google Maps](https://www.google.com/maps?q=17.05973,81.86922)\n\n"
                "You can also ask:\n"
                "- 'Directions to [place]' for navigation\n"
                "- 'Where is [place]' to find a specific location"
            )
        
        # Check for directions request patterns
        # 1. Standard "from A to B" pattern
        if from_to_match := re.search(from_to_pattern, user_message):
            start_str, end_str = from_to_match.groups()
            start = find_location(start_str)
            end = find_location(end_str)
        
        # 2. Simple "A to B" pattern
        elif simple_match := re.search(simple_directions_pattern, user_message):
            start_str, end_str = simple_match.groups()
            start = find_location(start_str)
            end = find_location(end_str)
        
        # 3. "To B" pattern (from current location)
        elif to_match := re.search(to_pattern, user_message):
            end_str = to_match.group(1)
            start = "gate"  # Default starting point
            end = find_location(end_str)
        
        # 4. Where pattern (single location query)
        elif where_match := re.search(where_pattern, user_message):
            loc_str = where_match.group(1).strip()
            location = find_location(loc_str)
            if location and location in campus_data:
                data = campus_data[location]
                response = f"📍 {location.capitalize()} is located at:\n"
                response += f"- Description: {data['description']}\n"
                if "hours" in data:
                    response += f"- Hours: {data['hours']}\n"
                
                # Nearby locations logic
                nearby = []
                for other_name, other_data in campus_data.items():
                    if other_name != location:
                        dist = calculate_distance(location, other_name)
                        if dist < 200:  # within 200 meters
                            nearby.append((other_name, dist))
                if nearby:
                    response += "\n📍 Nearby locations:\n"
                    for name, dist in sorted(nearby, key=lambda x: x[1])[:3]:
                        response += f"- {name.capitalize()} ({dist:.0f}m)\n"
            else:
                response = f"❌ Sorry, I couldn't find '{loc_str}'. Try asking about specific campus locations."
            return response
    
        # Generate directions if we have both points
        if start and end:
            if end not in campus_data:
                return f"❌ Sorry, I couldn't find '{end}' in campus locations."
            if start not in campus_data:
                return f"❌ Sorry, I couldn't find '{start}' in campus locations."
                
            return generate_directions(start, end)
                
        # No pattern matched
        return (
            "🤔 I'm not sure what you're asking. I can help with:\n"
            "- Directions (e.g., 'How to go from main block to library')\n"
            "- Finding places (e.g., 'Where is the cafeteria?')\n"
            "- Information about locations\n"
            "- Campus map (say 'show map')\n"
            "Try one of these or say 'help' for options."
        )
    
    except Exception as e:
        return f"❌ Sorry, I encountered an error: {str(e)}. Please try again."

def text_to_speech(text, lang='en'):
    """Convert text to speech and return the audio file path"""
    audio_dir = "audio_files"
    os.makedirs(audio_dir, exist_ok=True)
    
    filename = f"{audio_dir}/response_{uuid.uuid4()}.mp3"
    tts = gTTS(text=text, lang=lang, slow=False)
    tts.save(filename)
    return filename

def speech_to_text(audio_file):
    """Convert speech to text using Google Speech Recognition"""
    recognizer = sr.Recognizer()
    
    with sr.AudioFile(audio_file) as source:
        try:
            recognizer.adjust_for_ambient_noise(source)
            audio_data = recognizer.record(source)
            return recognizer.recognize_google(audio_data, language='en-IN')
        except sr.UnknownValueError:
            return "Could not understand audio"
        except sr.RequestError:
            return "Speech service error"
        except Exception as e:
            return f"Error: {str(e)}"

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat_handler():
    user_message = request.json['message']
    response = process_message(user_message)
    return jsonify({"response": response})

@app.route('/voice', methods=['POST'])
def voice_handler():
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file"}), 400
        
    audio_file = request.files['audio']
    temp_dir = "temp_audio"
    os.makedirs(temp_dir, exist_ok=True)
        
    temp_audio = f"{temp_dir}/input_{uuid.uuid4()}.wav"
    audio_file.save(temp_audio)
    
    user_message = speech_to_text(temp_audio)
    os.remove(temp_audio)
    
    response_text = process_message(user_message)
    audio_filename = text_to_speech(response_text)
    audio_url = os.path.basename(audio_filename)
    
    return jsonify({
        "user_message": user_message,
        "response": response_text,
        "audio_url": f"/audio/{audio_url}"
    })

@app.route('/audio/<filename>')
def get_audio(filename):
    return send_file(f"audio_files/{filename}", mimetype='audio/mpeg')

@app.route('/map')
def campus_map():
    return jsonify(campus_data)

if __name__ == '__main__':
    # Create directories if needed
    os.makedirs("audio_files", exist_ok=True)
    os.makedirs("temp_audio", exist_ok=True)
    
    # Clean up old audio files
    for file in os.listdir('audio_files'):
        if file.endswith('.mp3'):
            try:
                os.remove(f"audio_files/{file}")
            except OSError:
                pass
                
    app.run(debug=True)