from flask import Flask, render_template, request, jsonify
import os

app = Flask(__name__)

# In-memory database (for now, we'll replace this later)
# This is a simple dictionary to store staff profiles.
staff_profiles = {}
next_staff_id = 1

# Ensure an 'uploads' directory exists
if not os.path.exists('uploads'):
    os.makedirs('uploads')

@app.route('/')
def index():
    """Renders the home page."""
    return render_template('base.html')

@app.route('/profile/new', methods=['GET'])
def new_profile_form():
    """Displays the form to create a new staff profile."""
    return render_template('profile_form.html')

@app.route('/api/profile', methods=['POST'])
def create_profile():
    """Handles the creation of a new staff profile."""
    global next_staff_id
    
    # In a real app, you would have much more robust validation and error handling.
    data = request.form
    
    # For demonstration, we'll just print the received data to the console.
    print("Received data:", data)

    # We would also handle the file upload here
    if 'photo' in request.files:
        photo = request.files['photo']
        if photo.filename != '':
            # In a real app, save the file with a secure filename
            # For now, we just confirm it was received.
            print("Photo received:", photo.filename)

    # Create a new profile entry
    new_profile = {
        'id': next_staff_id,
        'first_name': data.get('first_name'),
        'last_name': data.get('last_name'),
        'nickname': data.get('nickname'),
        'phone': data.get('phone'),
        'instagram': data.get('instagram'),
        'facebook': data.get('facebook'),
        'line_id': data.get('line_id'),
        'dob': data.get('dob'), # Date of Birth
        'height': data.get('height'),
        'weight': data.get('weight'),
    }
    
    staff_profiles[next_staff_id] = new_profile
    next_staff_id += 1
    
    # Return a success response
    return jsonify({'status': 'success', 'message': 'Profile created successfully!', 'profile': new_profile}), 201


if __name__ == '__main__':
    app.run(debug=True, port=5000)