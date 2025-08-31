from app import create_app, db
from app.models import User, Agency

app = create_app()

with app.app_context():
    print("=== USERS IN DATABASE ===")
    users = User.query.all()
    for user in users:
        print(f"ID: {user.id}, Username: {user.username}, Role: {user.role}, Agency: {user.agency.name if user.agency else 'None'}")
    
    print("\n=== AGENCIES IN DATABASE ===")
    agencies = Agency.query.all()
    for agency in agencies:
        print(f"ID: {agency.id}, Name: {agency.name}")
    
    print("\n=== AVAILABLE ROLES ===")
    from app.models import UserRole
    for role in UserRole:
        print(f"Role: {role.value}")
