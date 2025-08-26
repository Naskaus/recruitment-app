from app import create_app, db
from app.models import User, Agency, Role

app = create_app()

with app.app_context():
    print("=== USERS IN DATABASE ===")
    users = User.query.all()
    for user in users:
        print(f"ID: {user.id}, Username: {user.username}, Role: {user.role.name if user.role else 'None'}, Agency: {user.agency.name if user.agency else 'None'}")
    
    print("\n=== AGENCIES IN DATABASE ===")
    agencies = Agency.query.all()
    for agency in agencies:
        print(f"ID: {agency.id}, Name: {agency.name}")
    
    print("\n=== ROLES IN DATABASE ===")
    roles = Role.query.all()
    for role in roles:
        print(f"ID: {role.id}, Name: {role.name}")
