# app/admin/routes.py

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, send_file, send_from_directory
from flask_login import login_required, current_user
from app.decorators import webdev_required, role_required
from app.models import Agency, User, UserRole, StaffProfile, Venue, AgencyPosition, AgencyContract, Assignment, PerformanceRecord, ContractCalculations
from app.services.agency_management_service import AgencyManagementService
from app import db

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

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
    agencies = Agency.query.all()
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
    agency = Agency.query.get_or_404(agency_id)
    data = request.get_json()
    
    if not data or 'name' not in data:
        return jsonify({'error': 'Nom de l\'agence requis'}), 400
    
    name = data['name'].strip()
    
    if not name:
        return jsonify({'error': 'Le nom de l\'agence ne peut pas être vide'}), 400
    
    # Vérifier si le nouveau nom existe déjà (sauf pour cette agence)
    existing_agency = Agency.query.filter_by(name=name).first()
    if existing_agency and existing_agency.id != agency_id:
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
    """API pour supprimer une agence"""
    agency = Agency.query.get_or_404(agency_id)
    
    # Vérifier si l'agence a des données associées
    users_count = User.query.filter_by(agency_id=agency_id).count()
    staff_count = agency.staff_profiles.count()
    venues_count = agency.venues.count()
    
    if users_count > 0 or staff_count > 0 or venues_count > 0:
        return jsonify({
            'error': f'Impossible de supprimer l\'agence "{agency.name}". Elle contient des données associées: {users_count} utilisateurs, {staff_count} profils staff, {venues_count} venues.'
        }), 400
    
    try:
        db.session.delete(agency)
        db.session.commit()
        
        return jsonify({'message': f'Agence "{agency.name}" supprimée avec succès'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Erreur lors de la suppression de l\'agence: {str(e)}'}), 500

@admin_bp.route('/api/agencies/<int:agency_id>/export', methods=['POST'])
@login_required
@webdev_required
def export_agency_data(agency_id):
    """API pour exporter les données d'une agence vers JSON"""
    try:
        result = AgencyManagementService.export_agency_data_to_json(agency_id)
        
        if result['success']:
            return jsonify({
                'message': f'Données de l\'agence exportées avec succès',
                'filename': result['filename'],
                'filepath': result['filepath'],
                'statistics': result['export_data']['statistics']
            })
        else:
            return jsonify({'error': result['error']}), 400
            
    except Exception as e:
        return jsonify({'error': f'Erreur lors de l\'export: {str(e)}'}), 500

@admin_bp.route('/api/agencies/<int:agency_id>/export/download/<filename>')
@login_required
@webdev_required
def download_agency_export(agency_id, filename):
    """Télécharger un fichier d'export d'agence"""
    try:
        import os
        from flask import current_app
        
        export_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'exports')
        filepath = os.path.join(export_dir, filename)
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'Fichier non trouvé'}), 404
        
        return send_file(
            filepath,
            as_attachment=True,
            download_name=filename,
            mimetype='application/json'
        )
        
    except Exception as e:
        return jsonify({'error': f'Erreur lors du téléchargement: {str(e)}'}), 500

@admin_bp.route('/api/agencies/<int:agency_id>/export/history')
@login_required
@webdev_required
def get_agency_export_history(agency_id):
    """Récupérer l'historique des exports pour une agence"""
    try:
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
    """Supprimer une agence"""
    try:
        # Récupérer l'agence
        agency = Agency.query.get(agency_id)
        if not agency:
            flash('Agence non trouvée', 'error')
            return redirect(url_for('admin.manage_agencies'))
        
        agency_name = agency.name
        
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
            
            # Supprimer les utilisateurs (sauf WEBDEV)
            User.query.filter(
                User.agency_id == agency_id,
                User.role != 'webdev'
            ).delete(synchronize_session=False)
            
            # Enfin, supprimer l'agence elle-même
            db.session.delete(agency)
            db.session.commit()
            
            flash(f'Agence "{agency_name}" supprimée avec succès.', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de la suppression des données: {str(e)}', 'error')
            return redirect(url_for('admin.manage_agencies'))
        
        return redirect(url_for('admin.manage_agencies'))
        
    except Exception as e:
        flash(f'Erreur lors de la suppression de l\'agence: {str(e)}', 'error')
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
        agency = Agency.query.get(agency_id)
        if not agency:
            return jsonify({'error': 'Agence non trouvée'}), 404
        
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
