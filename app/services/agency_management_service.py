# app/services/agency_management_service.py

import json
import os
from datetime import datetime
from flask import current_app
from app.models import Agency, User, StaffProfile, Venue, AgencyPosition, AgencyContract, Assignment, PerformanceRecord, ContractCalculations
from app import db

class AgencyManagementService:
    """Service pour la gestion des agences et l'export des données"""
    
    @staticmethod
    def export_agency_data_to_json(agency_id):
        """
        Exporte toutes les données liées à une agence vers un fichier JSON
        
        Args:
            agency_id (int): ID de l'agence à exporter
            
        Returns:
            dict: Dictionnaire contenant le statut de l'opération et le chemin du fichier
        """
        try:
            # Récupérer l'agence active uniquement
            agency = Agency.query.filter_by(id=agency_id, is_deleted=False).first()
            if not agency:
                return {
                    'success': False,
                    'error': f"Agence avec l'ID {agency_id} non trouvée ou supprimée"
                }
            
            # Structure des données à exporter
            export_data = {
                'export_info': {
                    'export_date': datetime.utcnow().isoformat(),
                    'agency_id': agency.id,
                    'agency_name': agency.name,
                    'export_version': '1.0'
                },
                'agency': AgencyManagementService._serialize_agency(agency),
                'users': AgencyManagementService._serialize_users(agency),
                'staff_profiles': AgencyManagementService._serialize_staff_profiles(agency),
                'venues': AgencyManagementService._serialize_venues(agency),
                'positions': AgencyManagementService._serialize_positions(agency),
                'contracts': AgencyManagementService._serialize_contracts(agency),
                'assignments': AgencyManagementService._serialize_assignments(agency),
                'performance_records': AgencyManagementService._serialize_performance_records(agency),
                'contract_calculations': AgencyManagementService._serialize_contract_calculations(agency),
                'statistics': AgencyManagementService._generate_statistics(agency)
            }
            
            # Créer le dossier d'export s'il n'existe pas
            export_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'exports')
            os.makedirs(export_dir, exist_ok=True)
            
            # Générer le nom du fichier
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"agency_{agency_id}_{agency.name.replace(' ', '_')}_{timestamp}.json"
            filepath = os.path.join(export_dir, filename)
            
            # Sauvegarder le fichier JSON
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)
            
            return {
                'success': True,
                'filepath': filepath,
                'filename': filename,
                'export_data': export_data
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Erreur lors de l\'export: {str(e)}'
            }
    
    @staticmethod
    def _serialize_agency(agency):
        """Sérialise les données de l'agence"""
        return {
            'id': agency.id,
            'name': agency.name,
            'created_at': agency.created_at.isoformat() if agency.created_at else None
        }
    
    @staticmethod
    def _serialize_users(agency):
        """Sérialise les utilisateurs de l'agence"""
        users = User.query.filter_by(agency_id=agency.id).all()
        return [{
            'id': user.id,
            'username': user.username,
            'role': user.role,
            'agency_id': user.agency_id,
            'created_at': user.id  # Pas de created_at dans le modèle User
        } for user in users]
    
    @staticmethod
    def _serialize_staff_profiles(agency):
        """Sérialise les profils staff de l'agence"""
        staff_profiles = agency.staff_profiles.all()
        return [{
            'id': staff.id,
            'staff_id': staff.staff_id,
            'first_name': staff.first_name,
            'last_name': staff.last_name,
            'nickname': staff.nickname,
            'phone': staff.phone,
            'instagram': staff.instagram,
            'facebook': staff.facebook,
            'line_id': staff.line_id,
            'dob': staff.dob.isoformat() if staff.dob else None,
            'height': staff.height,
            'weight': staff.weight,
            'status': staff.status,
            'photo_url': staff.photo_url,
            'admin_mama_name': staff.admin_mama_name,
            'created_at': staff.created_at.isoformat() if staff.created_at else None,
            'preferred_position': staff.preferred_position,
            'notes': staff.notes,
            'age': staff.age
        } for staff in staff_profiles]
    
    @staticmethod
    def _serialize_venues(agency):
        """Sérialise les venues de l'agence"""
        venues = agency.venues.all()
        return [{
            'id': venue.id,
            'name': venue.name,
            'logo_url': venue.logo_url,
            'agency_id': venue.agency_id
        } for venue in venues]
    
    @staticmethod
    def _serialize_positions(agency):
        """Sérialise les positions de l'agence"""
        positions = agency.positions.all()
        return [{
            'id': position.id,
            'name': position.name,
            'agency_id': position.agency_id,
            'created_at': position.created_at.isoformat() if position.created_at else None
        } for position in positions]
    
    @staticmethod
    def _serialize_contracts(agency):
        """Sérialise les contrats de l'agence"""
        contracts = agency.contracts.all()
        return [{
            'id': contract.id,
            'name': contract.name,
            'days': contract.days,
            'agency_id': contract.agency_id,
            'late_cutoff_time': contract.late_cutoff_time,
            'first_minute_penalty': contract.first_minute_penalty,
            'additional_minute_penalty': contract.additional_minute_penalty,
            'drink_price': contract.drink_price,
            'staff_commission': contract.staff_commission,
            'created_at': contract.created_at.isoformat() if contract.created_at else None
        } for contract in contracts]
    
    @staticmethod
    def _serialize_assignments(agency):
        """Sérialise les assignments de l'agence"""
        assignments = Assignment.query.filter_by(agency_id=agency.id).all()
        return [{
            'id': assignment.id,
            'agency_id': assignment.agency_id,
            'staff_id': assignment.staff_id,
            'managed_by_user_id': assignment.managed_by_user_id,
            'archived_staff_name': assignment.archived_staff_name,
            'archived_staff_photo': assignment.archived_staff_photo,
            'venue_id': assignment.venue_id,
            'venue_name': assignment.venue.name if assignment.venue else None,
            'contract_role': assignment.contract_role,
            'contract_type': assignment.contract_type,
            'start_date': assignment.start_date.isoformat() if assignment.start_date else None,
            'end_date': assignment.end_date.isoformat() if assignment.end_date else None,
            'base_salary': assignment.base_salary,
            'status': assignment.status,
            'created_at': assignment.created_at.isoformat() if assignment.created_at else None
        } for assignment in assignments]
    
    @staticmethod
    def _serialize_performance_records(agency):
        """Sérialise les enregistrements de performance de l'agence"""
        # Récupérer tous les assignments de l'agence
        assignment_ids = [a.id for a in Assignment.query.filter_by(agency_id=agency.id).all()]
        
        if not assignment_ids:
            return []
        
        # Récupérer tous les enregistrements de performance pour ces assignments
        performance_records = PerformanceRecord.query.filter(
            PerformanceRecord.assignment_id.in_(assignment_ids)
        ).all()
        
        return [{
            'id': record.id,
            'assignment_id': record.assignment_id,
            'record_date': record.record_date.isoformat() if record.record_date else None,
            'arrival_time': record.arrival_time.strftime('%H:%M') if record.arrival_time else None,
            'departure_time': record.departure_time.strftime('%H:%M') if record.departure_time else None,
            'drinks_sold': record.drinks_sold,
            'special_commissions': record.special_commissions,
            'bonus': record.bonus,
            'malus': record.malus,
            'lateness_penalty': record.lateness_penalty,
            'daily_salary': record.daily_salary,
            'daily_profit': record.daily_profit,
            'created_at': record.created_at.isoformat() if record.created_at else None
        } for record in performance_records]
    
    @staticmethod
    def _serialize_contract_calculations(agency):
        """Sérialise les calculs de contrats de l'agence"""
        # Récupérer tous les assignments de l'agence
        assignment_ids = [a.id for a in Assignment.query.filter_by(agency_id=agency.id).all()]
        
        if not assignment_ids:
            return []
        
        # Récupérer tous les calculs de contrats pour ces assignments
        contract_calculations = ContractCalculations.query.filter(
            ContractCalculations.assignment_id.in_(assignment_ids)
        ).all()
        
        return [{
            'id': calc.id,
            'assignment_id': calc.assignment_id,
            'total_salary': calc.total_salary,
            'total_commission': calc.total_commission,
            'total_profit': calc.total_profit,
            'days_worked': calc.days_worked,
            'total_drinks': calc.total_drinks,
            'total_special_comm': calc.total_special_comm,
            'last_updated': calc.last_updated.isoformat() if calc.last_updated else None
        } for calc in contract_calculations]
    
    @staticmethod
    def _generate_statistics(agency):
        """Génère des statistiques pour l'agence"""
        users_count = User.query.filter_by(agency_id=agency.id).count()
        staff_count = agency.staff_profiles.count()
        venues_count = agency.venues.count()
        positions_count = agency.positions.count()
        contracts_count = agency.contracts.count()
        assignments_count = Assignment.query.filter_by(agency_id=agency.id).count()
        
        # Compter les assignments par statut
        active_assignments = Assignment.query.filter_by(agency_id=agency.id, status='active').count()
        completed_assignments = Assignment.query.filter_by(agency_id=agency.id, status='completed').count()
        
        # Compter les enregistrements de performance
        assignment_ids = [a.id for a in Assignment.query.filter_by(agency_id=agency.id).all()]
        performance_records_count = 0
        if assignment_ids:
            performance_records_count = PerformanceRecord.query.filter(
                PerformanceRecord.assignment_id.in_(assignment_ids)
            ).count()
        
        return {
            'total_users': users_count,
            'total_staff': staff_count,
            'total_venues': venues_count,
            'total_positions': positions_count,
            'total_contracts': contracts_count,
            'total_assignments': assignments_count,
            'active_assignments': active_assignments,
            'completed_assignments': completed_assignments,
            'total_performance_records': performance_records_count,
            'export_timestamp': datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def get_agency_export_history(agency_id):
        """Récupère l'historique des exports pour une agence"""
        export_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'exports')
        
        if not os.path.exists(export_dir):
            return []
        
        exports = []
        for filename in os.listdir(export_dir):
            if filename.startswith(f"agency_{agency_id}_") and filename.endswith('.json'):
                filepath = os.path.join(export_dir, filename)
                file_stat = os.stat(filepath)
                exports.append({
                    'filename': filename,
                    'filepath': filepath,
                    'size_bytes': file_stat.st_size,
                    'created_at': datetime.fromtimestamp(file_stat.st_ctime).isoformat(),
                    'modified_at': datetime.fromtimestamp(file_stat.st_mtime).isoformat()
                })
        
        # Trier par date de création (plus récent en premier)
        exports.sort(key=lambda x: x['created_at'], reverse=True)
        return exports
    
    @staticmethod
    def delete_export_file(filepath):
        """Supprime un fichier d'export"""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                return {'success': True, 'message': 'Fichier supprimé avec succès'}
            else:
                return {'success': False, 'error': 'Fichier non trouvé'}
        except Exception as e:
            return {'success': False, 'error': f'Erreur lors de la suppression: {str(e)}'}

    @staticmethod
    def import_agency_data(data: dict):
        """Importe une agence et toutes ses données associées à partir d'un dictionnaire JSON.

        Le format attendu correspond à la sortie de export_agency_data_to_json:
        - 'agency': {...}
        - 'users': [...]
        - 'staff_profiles': [...]
        - 'venues': [...]
        - 'positions': [...]
        - 'contracts': [...]
        - 'assignments': [...]
        - 'performance_records': [...]
        - 'contract_calculations': [...]

        Returns: dict(success: bool, agency_id, created: {...}, warnings: [...])
        """
        from app.models import Agency, User, UserRole, StaffProfile, Venue, AgencyPosition, AgencyContract, Assignment, PerformanceRecord, ContractCalculations
        from app import db

        def _parse_date(val):
            if not val:
                return None
            try:
                # Accept both date and datetime iso strings
                return datetime.fromisoformat(val).date() if 'T' in val else datetime.strptime(val, '%Y-%m-%d').date()
            except Exception:
                try:
                    return datetime.fromisoformat(val).date()
                except Exception:
                    return None

        def _parse_time(val):
            if not val:
                return None
            try:
                return datetime.strptime(val, '%H:%M').time()
            except Exception:
                return None

        def _parse_dt(val):
            if not val:
                return None
            try:
                return datetime.fromisoformat(val)
            except Exception:
                return None

        # Some exports may wrap content; support both root forms
        content = data
        if isinstance(data, dict) and 'agency' not in data and 'export_data' in data:
            content = data.get('export_data') or data

        if not isinstance(content, dict) or 'agency' not in content:
            return {'success': False, 'error': "Format d'import invalide: clé 'agency' manquante"}

        warnings = []
        created_counts = {
            'users': 0,
            'staff_profiles': 0,
            'venues': 0,
            'positions': 0,
            'contracts': 0,
            'assignments': 0,
            'performance_records': 0,
            'contract_calculations': 0,
        }

        # ID remapping tables (old -> new)
        idmap = {
            'user': {},
            'staff': {},
            'venue': {},
            'position': {},
            'contract': {},
            'assignment': {},
        }

        try:
            # Start a transaction
            # 1) Create Agency (ensure name uniqueness)
            agency_payload = content['agency']
            base_name = (agency_payload.get('name') or 'Imported Agency').strip()
            name_candidate = base_name
            suffix_idx = 1
            while Agency.query.filter_by(name=name_candidate).first() is not None:
                name_candidate = f"{base_name} (Imported {datetime.utcnow().strftime('%Y%m%d_%H%M%S')})" if suffix_idx == 1 else f"{base_name} (Imported {suffix_idx})"
                suffix_idx += 1

            new_agency = Agency(name=name_candidate)
            db.session.add(new_agency)
            db.session.flush()  # get new_agency.id without full commit

            # 2) Users
            for u in content.get('users', []) or []:
                try:
                    username = u.get('username')
                    role = u.get('role') or UserRole.ADMIN.value
                    if not username:
                        warnings.append('Utilisateur sans username ignoré')
                        continue
                    # Avoid username collision globally; append suffix if needed
                    user_candidate = username
                    i = 1
                    while User.query.filter_by(username=user_candidate).first() is not None:
                        user_candidate = f"{username}_{i}"
                        i += 1
                    new_user = User(username=user_candidate, role=role, agency_id=new_agency.id)
                    # Set a temporary password (must be changed later)
                    try:
                        new_user.set_password('TempPass123!')
                    except Exception:
                        pass
                    db.session.add(new_user)
                    db.session.flush()
                    idmap['user'][u.get('id')] = new_user.id
                    created_counts['users'] += 1
                except Exception as ue:
                    warnings.append(f"User import error for '{u.get('username')}': {ue}")

            # 3) Venues
            for v in content.get('venues', []) or []:
                try:
                    new_v = Venue(
                        name=v.get('name'),
                        logo_url=v.get('logo_url'),
                        agency_id=new_agency.id,
                    )
                    db.session.add(new_v)
                    db.session.flush()
                    idmap['venue'][v.get('id')] = new_v.id
                    created_counts['venues'] += 1
                except Exception as ve:
                    warnings.append(f"Venue import error for '{v.get('name')}': {ve}")

            # 4) Positions
            for p in content.get('positions', []) or []:
                try:
                    new_p = AgencyPosition(
                        name=p.get('name'),
                        agency_id=new_agency.id,
                        created_at=_parse_dt(p.get('created_at')),
                    )
                    db.session.add(new_p)
                    db.session.flush()
                    idmap['position'][p.get('id')] = new_p.id
                    created_counts['positions'] += 1
                except Exception as pe:
                    warnings.append(f"Position import error for '{p.get('name')}': {pe}")

            # 5) Contracts
            for c in content.get('contracts', []) or []:
                try:
                    new_c = AgencyContract(
                        name=c.get('name'),
                        days=c.get('days'),
                        agency_id=new_agency.id,
                        late_cutoff_time=c.get('late_cutoff_time'),
                        first_minute_penalty=c.get('first_minute_penalty'),
                        additional_minute_penalty=c.get('additional_minute_penalty'),
                        drink_price=c.get('drink_price'),
                        staff_commission=c.get('staff_commission'),
                        created_at=_parse_dt(c.get('created_at')),
                    )
                    db.session.add(new_c)
                    db.session.flush()
                    idmap['contract'][c.get('id')] = new_c.id
                    created_counts['contracts'] += 1
                except Exception as ce:
                    warnings.append(f"Contract import error for '{c.get('name')}': {ce}")

            # 6) Staff Profiles
            for s in content.get('staff_profiles', []) or []:
                try:
                    new_s = StaffProfile(
                        agency_id=new_agency.id,
                        staff_id=s.get('staff_id'),
                        first_name=s.get('first_name'),
                        last_name=s.get('last_name'),
                        nickname=s.get('nickname'),
                        phone=s.get('phone'),
                        instagram=s.get('instagram'),
                        facebook=s.get('facebook'),
                        line_id=s.get('line_id'),
                        dob=_parse_date(s.get('dob')),
                        height=s.get('height'),
                        weight=s.get('weight'),
                        status=s.get('status'),
                        photo_url=s.get('photo_url'),
                        admin_mama_name=s.get('admin_mama_name'),
                        created_at=_parse_dt(s.get('created_at')),
                        preferred_position=s.get('preferred_position'),
                        notes=s.get('notes'),
                    )
                    db.session.add(new_s)
                    db.session.flush()
                    idmap['staff'][s.get('id')] = new_s.id
                    created_counts['staff_profiles'] += 1
                except Exception as se:
                    warnings.append(f"Staff import error for '{s.get('nickname') or s.get('first_name')}': {se}")

            # 7) Assignments
            for a in content.get('assignments', []) or []:
                try:
                    new_a = Assignment(
                        agency_id=new_agency.id,
                        staff_id=idmap['staff'].get(a.get('staff_id')),
                        managed_by_user_id=idmap['user'].get(a.get('managed_by_user_id')),
                        archived_staff_name=a.get('archived_staff_name'),
                        archived_staff_photo=a.get('archived_staff_photo'),
                        venue_id=idmap['venue'].get(a.get('venue_id')),
                        contract_role=a.get('contract_role'),
                        contract_type=a.get('contract_type'),
                        start_date=_parse_date(a.get('start_date')),
                        end_date=_parse_date(a.get('end_date')),
                        base_salary=a.get('base_salary'),
                        status=a.get('status') or 'active',
                        created_at=_parse_dt(a.get('created_at')),
                    )
                    db.session.add(new_a)
                    db.session.flush()
                    idmap['assignment'][a.get('id')] = new_a.id
                    created_counts['assignments'] += 1
                except Exception as ae:
                    warnings.append(f"Assignment import error (staff_id={a.get('staff_id')}): {ae}")

            # 8) Performance Records
            for r in content.get('performance_records', []) or []:
                try:
                    new_r = PerformanceRecord(
                        assignment_id=idmap['assignment'].get(r.get('assignment_id')),
                        record_date=_parse_date(r.get('record_date')),
                        arrival_time=_parse_time(r.get('arrival_time')),
                        departure_time=_parse_time(r.get('departure_time')),
                        drinks_sold=r.get('drinks_sold'),
                        special_commissions=r.get('special_commissions'),
                        bonus=r.get('bonus'),
                        malus=r.get('malus'),
                        lateness_penalty=r.get('lateness_penalty'),
                        daily_salary=r.get('daily_salary'),
                        daily_profit=r.get('daily_profit'),
                        created_at=_parse_dt(r.get('created_at')),
                    )
                    # Skip if assignment missing (dangling)
                    if new_r.assignment_id is None:
                        warnings.append('Performance record ignoré: assignment introuvable dans l\'import')
                        continue
                    db.session.add(new_r)
                    created_counts['performance_records'] += 1
                except Exception as re:
                    warnings.append(f"Performance import error (assignment_id={r.get('assignment_id')}): {re}")

            # 9) Contract Calculations
            for ccalc in content.get('contract_calculations', []) or []:
                try:
                    new_calc = ContractCalculations(
                        assignment_id=idmap['assignment'].get(ccalc.get('assignment_id')),
                        total_salary=ccalc.get('total_salary'),
                        total_commission=ccalc.get('total_commission'),
                        total_profit=ccalc.get('total_profit'),
                        days_worked=ccalc.get('days_worked'),
                        total_drinks=ccalc.get('total_drinks'),
                        total_special_comm=ccalc.get('total_special_comm'),
                        last_updated=_parse_dt(ccalc.get('last_updated')),
                    )
                    if new_calc.assignment_id is None:
                        warnings.append("Contract calculation ignoré: assignment introuvable dans l'import")
                        continue
                    db.session.add(new_calc)
                    created_counts['contract_calculations'] += 1
                except Exception as ce2:
                    warnings.append(f"Contract calculation import error (assignment_id={ccalc.get('assignment_id')}): {ce2}")

            db.session.commit()

            return {
                'success': True,
                'agency_id': new_agency.id,
                'agency_name': new_agency.name,
                'created': created_counts,
                'warnings': warnings,
            }

        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': f"Erreur lors de l'import: {str(e)}", 'warnings': warnings}
