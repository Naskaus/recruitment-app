# app/admin/routes.py

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, send_file, send_from_directory, current_app
from flask_login import login_required, current_user
from app.decorators import webdev_required, role_required, admin_required
from app.models import Agency, User, UserRole, StaffProfile, Venue, AgencyPosition, AgencyContract, Assignment, PerformanceRecord, ContractCalculations
from app.services.agency_management_service import AgencyManagementService

from app import db
import subprocess
import time
from sqlalchemy import func

admin_bp = Blueprint('admin', __name__, template_folder='../templates', url_prefix='/admin')

@admin_bp.route('/manage_agencies')
@login_required
@webdev_required
def manage_agencies():
    """Page de gestion des agences - accessible uniquement aux WEBDEV"""
    agencies = Agency.query.all()
    
    # Préparer les données des agences avec les statistiques
    agencies_data = []
    for agency in agencies:
        users_count = User.query.filter_by(agency_id=agency.id).count()
        staff_count = agency.staff_profiles.count()
        venues_count = agency.venues.count()
        
        agencies_data.append({
            'id': agency.id,
            'name': agency.name,
            'created_at': agency.created_at,
            'is_deleted': agency.is_deleted,
            'users_count': users_count,
            'staff_count': staff_count,
            'venues_count': venues_count
        })
    
    return render_template('admin/manage_agencies.html', agencies=agencies_data)

@admin_bp.route('/api/agencies', methods=['GET'])
@login_required
@webdev_required
def get_agencies():
    """API pour récupérer la liste des agences"""
    agencies = Agency.query.filter_by(is_deleted=False).all()
    agencies_data = []
    
    for agency in agencies:
        # Compter les utilisateurs par rôle pour cette agence
        users_count = User.query.filter_by(agency_id=agency.id).count()
        staff_count = agency.staff_profiles.count()
        venues_count = agency.venues.count()
        
        agencies_data.append({
            'id': agency.id,
            'name': agency.name,
            'created_at': agency.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'users_count': users_count,
            'staff_count': staff_count,
            'venues_count': venues_count
        })
    
    return jsonify({'agencies': agencies_data})

@admin_bp.route('/api/agencies', methods=['POST'])
@login_required
@webdev_required
def create_agency():
    """API pour créer une nouvelle agence"""
    data = request.get_json()
    
    if not data or 'name' not in data:
        return jsonify({'error': 'Nom de l\'agence requis'}), 400
    
    name = data['name'].strip()
    
    if not name:
        return jsonify({'error': 'Le nom de l\'agence ne peut pas être vide'}), 400
    
    # Vérifier si l'agence existe déjà
    existing_agency = Agency.query.filter_by(name=name).first()
    if existing_agency:
        return jsonify({'error': f'Une agence avec le nom "{name}" existe déjà'}), 400
    
    try:
        new_agency = Agency(name=name)
        db.session.add(new_agency)
        db.session.commit()
        
        return jsonify({
            'message': f'Agence "{name}" créée avec succès',
            'agency': {
                'id': new_agency.id,
                'name': new_agency.name,
                'created_at': new_agency.created_at.strftime('%Y-%m-%d %H:%M:%S')
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Erreur lors de la création de l\'agence: {str(e)}'}), 500

@admin_bp.route('/api/agencies/<int:agency_id>', methods=['PUT'])
@login_required
@webdev_required
def update_agency(agency_id):
    """API pour modifier une agence"""
    agency = Agency.query.filter_by(id=agency_id, is_deleted=False).first()
    if not agency:
        return jsonify({'error': 'This agency no longer exists. Please contact your manager.'}), 403
    data = request.get_json()
    
    if not data or 'name' not in data:
        return jsonify({'error': 'Nom de l\'agence requis'}), 400
    
    name = data['name'].strip()
    
    if not name:
        return jsonify({'error': 'Le nom de l\'agence ne peut pas être vide'}), 400
    
    # Vérifier si le nouveau nom existe déjà (sauf pour cette agence)
    existing_agency = Agency.query.filter(Agency.name == name, Agency.id != agency_id, Agency.is_deleted == False).first()
    if existing_agency:
        return jsonify({'error': f'Une agence avec le nom "{name}" existe déjà'}), 400
    
    try:
        agency.name = name
        db.session.commit()
        
        return jsonify({
            'message': f'Agence "{name}" mise à jour avec succès',
            'agency': {
                'id': agency.id,
                'name': agency.name,
                'created_at': agency.created_at.strftime('%Y-%m-%d %H:%M:%S')
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Erreur lors de la mise à jour de l\'agence: {str(e)}'}), 500

@admin_bp.route('/api/agencies/<int:agency_id>', methods=['DELETE'])
@login_required
@webdev_required
def delete_agency(agency_id):
    """API pour marquer une agence comme supprimée"""
    agency = Agency.query.filter_by(id=agency_id, is_deleted=False).first()
    if not agency:
        return jsonify({'error': 'This agency no longer exists. Please contact your manager.'}), 403
    
    # Vérifier si l'agence n'est pas déjà marquée comme supprimée
    if agency.is_deleted:
        return jsonify({'error': f'L\'agence "{agency.name}" est déjà marquée comme supprimée'}), 400
    
    try:
        # Marquer l'agence comme supprimée au lieu de la supprimer physiquement
        agency.is_deleted = True
        db.session.commit()
        return jsonify({
            'message': f'Agence "{agency.name}" marquée comme supprimée avec succès',
            'is_deleted': True
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Erreur lors de la suppression de l\'agence: {str(e)}'}), 500

@admin_bp.route('/api/agencies/<int:agency_id>/export', methods=['POST'])
@login_required
@webdev_required
def export_agency_data(agency_id):
    """API pour exporter les données d'une agence vers JSON"""
    try:
        # Ensure agency is active
        a = Agency.query.filter_by(id=agency_id, is_deleted=False).first()
        if not a:
            return jsonify({'error': 'This agency no longer exists. Please contact your manager.'}), 403
        result = AgencyManagementService.export_agency_data_to_json(agency_id)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': f'Données de l\'agence exportées avec succès',
                'filename': result['filename'],
                'filepath': result['filepath'],
                'statistics': result['export_data']['statistics']
            })
        else:
            return jsonify({'error': result['error']}), 400
            
    except Exception as e:
        return jsonify({'error': f'Erreur lors de l\'export: {str(e)}'}), 500

@admin_bp.route('/api/agencies/<int:agency_id>/export/download/<path:filename>')
@login_required
@webdev_required
def download_export_file(agency_id, filename):
    """Sert un fichier d'export pour le téléchargement"""
    try:
        import os
        from flask import current_app
        
        export_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'exports')
        
        # Vérifier que le fichier existe et appartient à l'agence
        if not filename.startswith(f"agency_{agency_id}_"):
            return jsonify({'error': 'Accès non autorisé à ce fichier.'}), 403
        
        return send_from_directory(
            directory=export_dir,
            path=filename,
            as_attachment=True,
            download_name=filename
        )
        
    except FileNotFoundError:
        return jsonify({'error': 'Fichier non trouvé.'}), 404
    except Exception as e:
        return jsonify({'error': f'Erreur lors du téléchargement: {str(e)}'}), 500

@admin_bp.route('/api/agencies/<int:agency_id>/export/history')
@login_required
@webdev_required
def get_agency_export_history(agency_id):
    """Récupérer l'historique des exports pour une agence"""
    try:
        # Verify active agency before listing history
        a = Agency.query.filter_by(id=agency_id, is_deleted=False).first()
        if not a:
            return jsonify({'error': 'This agency no longer exists. Please contact your manager.'}), 403
        exports = AgencyManagementService.get_agency_export_history(agency_id)
        return jsonify({'exports': exports})
        
    except Exception as e:
        return jsonify({'error': f'Erreur lors de la récupération de l\'historique: {str(e)}'}), 500

@admin_bp.route('/api/agencies/export/delete', methods=['DELETE'])
@login_required
@webdev_required
def delete_export_file():
    """Supprimer un fichier d'export"""
    try:
        data = request.get_json()
        filepath = data.get('filepath')
        
        if not filepath:
            return jsonify({'error': 'Chemin du fichier requis'}), 400
        
        result = AgencyManagementService.delete_export_file(filepath)
        
        if result['success']:
            return jsonify({'message': result['message']})
        else:
            return jsonify({'error': result['error']}), 400
            
    except Exception as e:
        return jsonify({'error': f'Erreur lors de la suppression: {str(e)}'}), 500

@admin_bp.route('/delete_agency/<int:agency_id>', methods=['POST'])
@login_required
@webdev_required
def delete_agency_post(agency_id):
    """Marquer une agence comme supprimée (soft delete)"""
    try:
        # Récupérer l'agence
        agency = Agency.query.filter_by(id=agency_id, is_deleted=False).first()
        if not agency:
            flash('Agency not found', 'error')
            # If the deleted agency was selected in session for WebDev, clear it
            try:
                from flask import session
                if session.get('current_agency_id') == agency_id:
                    session.pop('current_agency_id', None)
                    session.pop('current_agency_name', None)
            except Exception:
                pass
            return redirect(url_for('admin.manage_agencies'))
        
        if agency.is_deleted:
            flash('This agency is already marked as deleted', 'warning')
            return redirect(url_for('admin.manage_agencies'))
        
        # Marquer l'agence comme supprimée
        agency.is_deleted = True
        db.session.commit()
        
        flash(f'Agency "{agency.name}" has been marked as deleted', 'success')
        return redirect(url_for('admin.manage_agencies'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error marking agency as deleted: {str(e)}', 'error')
        return redirect(url_for('admin.manage_agencies'))

@admin_bp.route('/api/agencies/import', methods=['POST'])
@login_required
@webdev_required
def import_agency():
    """Receive and process uploaded agency JSON file."""
    file = request.files.get('file')
    if not file:
        flash('No file provided.', 'error')
        return redirect(url_for('admin.manage_agencies'))
    # Basic content-type / extension check
    if not (file.mimetype in ('application/json',) or (file.filename and file.filename.lower().endswith('.json'))):
        flash('Invalid file type. Please upload a .json file.', 'error')
        return redirect(url_for('admin.manage_agencies'))

    try:
        raw = file.read()
        if not raw:
            flash('Uploaded file is empty.', 'error')
            return redirect(url_for('admin.manage_agencies'))
        import json
        payload = json.loads(raw)
    except Exception as e:
        flash(f'Invalid JSON file: {str(e)}', 'error')
        return redirect(url_for('admin.manage_agencies'))

    # Call service to import
    try:
        result = AgencyManagementService.import_agency_data(payload)
        if not result.get('success'):
            flash(f"Import failed: {result.get('error', 'Unknown error')}", 'error')
            return redirect(url_for('admin.manage_agencies'))
        created = result.get('created', {})
        warnings = result.get('warnings', [])
        summary = (
            f"Agency '{result.get('agency_name')}' imported successfully. "
            f"Users: {created.get('users',0)}, Staff: {created.get('staff_profiles',0)}, Venues: {created.get('venues',0)}, "
            f"Positions: {created.get('positions',0)}, Contracts: {created.get('contracts',0)}, Assignments: {created.get('assignments',0)}."
        )
        flash(summary, 'success')
        if warnings:
            flash(f"Warnings: {'; '.join(warnings[:5])}{' ...' if len(warnings)>5 else ''}", 'warning')
    except Exception as e:
        flash(f'Unexpected error during import: {str(e)}', 'error')
    return redirect(url_for('admin.manage_agencies'))
@admin_bp.route('/force_delete_agency/<int:agency_id>', methods=['POST'])
@login_required
@webdev_required
def force_delete_agency(agency_id):
    """Supprimer définitivement une agence avec sauvegarde préalable"""
    try:
        # Récupérer l'agence
        # Allow force-delete regardless of current soft-delete state
        agency = Agency.query.get(agency_id)
        if not agency:
            flash('Agency not found', 'error')
            return redirect(url_for('admin.manage_agencies'))
        
        # Créer une sauvegarde avant suppression
        try:
            # Créer un dossier pour les sauvegardes si nécessaire
            import os
            from datetime import datetime
            
            backup_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            
            # Nom du fichier de sauvegarde
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f'agency_{agency_id}_backup_{timestamp}.sqlite'
            backup_path = os.path.join(backup_dir, backup_filename)
            
            # Copier la base de données actuelle comme sauvegarde
            import shutil
            from config import basedir
            
            db_path = os.path.join(basedir, 'data', 'recruitment-dev.db')
            shutil.copy2(db_path, backup_path)
            
            flash(f'Backup created successfully: {backup_filename}', 'info')
            
        except Exception as backup_error:
            db.session.rollback()
            flash(f'Error creating backup: {str(backup_error)}', 'error')
            return redirect(url_for('admin.manage_agencies'))
        
        # Supprimer toutes les données associées à l'agence
        try:
            # Supprimer les calculs de contrats
            assignment_ids = [a.id for a in Assignment.query.filter_by(agency_id=agency_id).all()]
            if assignment_ids:
                ContractCalculations.query.filter(
                    ContractCalculations.assignment_id.in_(assignment_ids)
                ).delete(synchronize_session=False)
                
                # Supprimer les enregistrements de performance
                PerformanceRecord.query.filter(
                    PerformanceRecord.assignment_id.in_(assignment_ids)
                ).delete(synchronize_session=False)
                
                # Supprimer les assignments
                Assignment.query.filter_by(agency_id=agency_id).delete(synchronize_session=False)
            
            # Supprimer les profils staff
            StaffProfile.query.filter_by(agency_id=agency_id).delete(synchronize_session=False)
            
            # Supprimer les venues
            Venue.query.filter_by(agency_id=agency_id).delete(synchronize_session=False)
            
            # Supprimer les positions
            AgencyPosition.query.filter_by(agency_id=agency_id).delete(synchronize_session=False)
            
            # Supprimer les contrats
            AgencyContract.query.filter_by(agency_id=agency_id).delete(synchronize_session=False)
            
            # Supprimer tous les utilisateurs de l'agence (y compris tout webdev mal assigné)
            User.query.filter(
                User.agency_id == agency_id
            ).delete(synchronize_session=False)
            
            # Enfin, supprimer l'agence elle-même
            db.session.delete(agency)
            db.session.commit()
            
            flash(f'Agency "{agency.name}" has been permanently deleted.', 'success')
            
        except Exception as delete_error:
            db.session.rollback()
            flash(f'Error during agency deletion: {str(delete_error)}', 'error')
            return redirect(url_for('admin.manage_agencies'))
        
        return redirect(url_for('admin.manage_agencies'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error processing agency deletion: {str(e)}', 'error')
        return redirect(url_for('admin.manage_agencies'))

@admin_bp.route('/download_backup/<path:filename>')
@login_required
@role_required('WEBDEV')
def download_backup(filename):
    """Télécharger un fichier de backup d'agence - accessible uniquement aux WEBDEV"""
    try:
        import os
        from flask import current_app
        
        # Définir le répertoire des exports/backups
        export_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'exports')
        
        # Vérifier que le fichier existe
        filepath = os.path.join(export_dir, filename)
        if not os.path.exists(filepath):
            flash('Fichier de backup non trouvé', 'error')
            return redirect(url_for('admin.manage_agencies'))
        
        # Utiliser send_from_directory pour un téléchargement sécurisé
        return send_from_directory(
            directory=export_dir,
            path=filename,
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        flash(f'Erreur lors du téléchargement du backup: {str(e)}', 'error')
        return redirect(url_for('admin.manage_agencies'))

@admin_bp.route('/export_and_download/<int:agency_id>')
@login_required
@role_required('WEBDEV')
def export_and_download(agency_id):
    """Exporter et télécharger immédiatement les données d'une agence"""
    try:
        # Récupérer l'agence
        agency = Agency.query.filter_by(id=agency_id, is_deleted=False).first()
        if not agency:
            return jsonify({'error': 'This agency no longer exists. Please contact your manager.'}), 403
        
        # Exporter les données de l'agence
        export_result = AgencyManagementService.export_agency_data_to_json(agency_id)
        
        if not export_result['success']:
            return jsonify({'error': f'Erreur lors de l\'export des données: {export_result["error"]}'}), 500
        
        # Récupérer les données exportées
        export_data = export_result['export_data']
        
        # Créer le nom de fichier pour le téléchargement
        filename = export_result['filename']
        
        # Retourner les données JSON directement avec les en-têtes de téléchargement
        response = jsonify(export_data)
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.headers['Content-Type'] = 'application/json'
        
        return response
        
    except Exception as e:
        return jsonify({'error': f'Erreur lors de l\'export et téléchargement: {str(e)}'}), 500

# Reactivate a soft-deleted agency
@admin_bp.route('/reactivate_agency/<int:agency_id>', methods=['POST'])
@login_required
@webdev_required
def reactivate_agency(agency_id):
    """Réactiver une agence (soft-delete -> active)"""
    try:
        agency = Agency.query.get_or_404(agency_id)
        if not agency.is_deleted:
            flash('Agency is already active', 'info')
            return redirect(url_for('admin.manage_agencies'))
        agency.is_deleted = False
        db.session.commit()
        flash(f'Agency "{agency.name}" has been reactivated', 'success')
        return redirect(url_for('admin.manage_agencies'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error reactivating agency: {str(e)}', 'error')
        return redirect(url_for('admin.manage_agencies'))

@admin_bp.route('/debug-vitals')
@login_required
@admin_required
def debug_vitals():
    """
    Endpoint de diagnostic pour vérifier la version du code et la performance de la DB.
    """
    # 1. Vérification de la version du code via Git
    try:
        commit_hash = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'],
            cwd='/home/Naskaus/recruitment-app'  # Chemin absolu du projet sur PythonAnywhere
        ).decode('utf-8').strip()
    except Exception as e:
        commit_hash = f"Error getting git hash: {str(e)}"

    # 2. Test de performance de la requête DB de base
    start_time = time.time()
    try:
        # Simule la requête initiale de la page payroll
        assignment_count = db.session.query(func.count(Assignment.id)).scalar()
        db_status = "OK"
    except Exception as e:
        assignment_count = -1
        db_status = f"Error connecting to DB: {str(e)}"
    end_time = time.time()

    db_query_time = (end_time - start_time) * 1000  # en ms

    # 3. Renvoyer les résultats
    return jsonify({
        'status': 'OK',
        'version_info': {
            'deployed_commit_hash': commit_hash
        },
        'database_vitals': {
            'status': db_status,
            'total_assignments_found': assignment_count,
            'query_time_ms': round(db_query_time, 2)
        }
    })



