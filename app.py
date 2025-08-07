from flask import Flask, render_template, request, jsonify
import os
from datetime import datetime

app = Flask(__name__)

# In-memory database, now with status and creation date
staff_profiles = {}
next_staff_id = 1

# Define status levels
STATUS_LEVELS = [
    "Active", "On assignment", "Quiet (recent)", "Moderately active", 
    "On holiday", "Inactive (long time)"
]

# Ensure an 'uploads' directory exists
if not os.path.exists('uploads'):
    os.makedirs('uploads')

@app.route('/')
def index():
    """Renders the home page, which will now be the staff list."""
    # The list() is important to avoid issues with modifying dicts during iteration
    all_profiles = list(staff_profiles.values())
    return render_template('staff_list.html', profiles=all_profiles, statuses=STATUS_LEVELS)

@app.route('/staff')
def staff_list():
    """Renders the page that lists all staff members."""
    all_profiles = list(staff_profiles.values())
    return render_template('staff_list.html', profiles=all_profiles, statuses=STATUS_LEVELS)

@app.route('/profile/new', methods=['GET'])
def new_profile_form():
    """Displays the form to create a new staff profile."""
    return render_template('profile_form.html')

@app.route('/api/profile', methods=['POST'])
def create_profile():
    """Handles the creation of a new staff profile."""
    global next_staff_id
    
    data = request.form
    
    # Calculate age from date of birth
    age = None
    if data.get('dob'):
        try:
            birth_date = datetime.strptime(data.get('dob'), '%Y-%m-%d')
            today = datetime.today()
            age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        except ValueError:
            age = None # Or handle error appropriately

    new_profile = {
        'id': next_staff_id,
        'first_name': data.get('first_name'),
        'last_name': data.get('last_name'),
        'nickname': data.get('nickname'),
        'phone': data.get('phone'),
        'instagram': data.get('instagram'),
        'facebook': data.get('facebook'),
        'line_id': data.get('line_id'),
        'dob': data.get('dob'),
        'age': age,
        'height': data.get('height'),
        'weight': data.get('weight'),
        'status': 'Active',  # Default status for new profiles
        'photo_url': 'https://via.placeholder.com/100' # Placeholder for now
    }
    
    # Handle photo upload
    if 'photo' in request.files:
        photo = request.files['photo']
        if photo.filename != '':
            print(f"Photo '{photo.filename}' received for profile {next_staff_id}.")

    staff_profiles[next_staff_id] = new_profile
    next_staff_id += 1
    
    return jsonify({'status': 'success', 'message': 'Profile created successfully!', 'profile': new_profile}), 201


if __name__ == '__main__':
    app.run(debug=True, port=5000)