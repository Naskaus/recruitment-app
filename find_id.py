# find_id.py
from app import create_app
from app.models import Assignment, StaffProfile

app = create_app()

with app.app_context():
    # Trouve le profil du staff avec le staff_id '007'
    staff_profile = StaffProfile.query.filter_by(staff_id='007').first()
    
    if staff_profile:
        # Trouve l'assignment actif pour ce staff
        assignment = Assignment.query.filter_by(staff_id=staff_profile.id, status='active').first()
        if assignment:
            print(f"SUCCÈS : L'Assignment ID pour le staff 'COYOTE' (Staff ID 007) est : {assignment.id}")
        else:
            print("ERREUR : Staff 'COYOTE' trouvé, mais aucun assignment actif associé.")
    else:
        print("ERREUR : Aucun staff trouvé avec le staff_id '007'.")
