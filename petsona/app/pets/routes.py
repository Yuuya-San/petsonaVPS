import os
from datetime import datetime
from slugify import slugify
from werkzeug.utils import secure_filename
from flask import (
    render_template, request, redirect,
    url_for, flash, abort, current_app
)
from flask_login import login_required, current_user

from app import db
from app.models import Species, Breed
from app.utils.audit import log_event
from . import bp
from app.utils.icons import get_species_icon
from sqlalchemy import func


@bp.route('/species')
@login_required
def species_index():
    page = request.args.get('page', 1, type=int)

    # Paginate active species
    pagination = Species.query.filter(
        Species.deleted_at.is_(None)
    ).order_by(Species.name.asc()).paginate(
        page=page, per_page=8, error_out=False
    )

    species_list = pagination.items

    # Count active breeds per species
    # Returns a dictionary {species_id: breed_count}
    breed_counts = dict(
        db.session.query(
            Breed.species_id,
            func.count(Breed.id)
        )
        .filter(Breed.is_active==True)  # only active breeds
        .group_by(Breed.species_id)
        .all()
    )
    

    # Attach count to each species for the template
    for species in species_list:
        species.active_breed_count = breed_counts.get(species.id, 0)


    return render_template(
        'pets/species_index.html',
        species_list=species_list,
        pagination=pagination,
        page_title="Pet Species"
    )


@bp.route('/species/save', methods=['POST'])
@login_required
def save_species():
    species_id = request.form.get('species_id')

    # ✅ IMPORTANT: distinguish EDIT vs CREATE
    if species_id:
        species = Species.query.get_or_404(species_id)
    else:
        species = Species()

    # ---- BASIC FIELDS ----
    species.name = request.form.get('name', '').strip()
    species.description = request.form.get('description', '').strip()
    species.legal_status = request.form.get('legal_status')

    # ---- AUTO ICON (SYSTEM CONTROLLED) ----
    species.icon = get_species_icon(species.name)

    # ---- IMAGE HANDLING ----
    file = request.files.get('image')
    if file and file.filename:
        filename = secure_filename(file.filename)
        path = f"uploads/species/{filename}"
        file.save(os.path.join(current_app.static_folder, path))
        species.image_url = path
    elif not species.image_url:
        species.image_url = 'uploads/no-image-attachment.jpg'

    # ---- SAVE ----
    db.session.add(species)
    db.session.commit()

    log_event(
        event='species.saved',
        details={'species_id': species.id, 'name': species.name}
    )

    flash('Species saved successfully.', 'success')
    return redirect(url_for('pets.species_index'))



@bp.route('/species/<int:id>/delete', methods=['POST'])
@login_required
def delete_species(id):
    species = Species.query.get_or_404(id)
    species.deleted_at = datetime.utcnow()
    db.session.commit()

    log_event(
        event='species.deleted',
        details={'species_id': species.id, 'name': species.name}
    )

    flash('Species deleted.', 'warning')
    return redirect(url_for('pets.species_index'))

@bp.route('/species/<int:id>')
@login_required
def view_species(id):
    species = Species.query.get_or_404(id)

    # Only fetch active breeds (not soft-deleted)
    breeds = Breed.query.filter_by(
        species_id=species.id,
        is_active=True   # exclude soft-deleted breeds
    ).order_by(Breed.name.asc()).all()

    return render_template(
        'pets/species_view.html',
        species=species,
        breeds=breeds,
        page_title=f"{species.name} Breeds"
    )

# -------------------
# SAVE BREED (ADD / EDIT)
# -------------------
@bp.route('/breed/save', methods=['POST'])
@login_required
def save_breed():
    breed_id = request.form.get('breed_id')
    species_id = request.form.get('species_id')

    if breed_id:
        breed = Breed.query.get(breed_id)
        if not breed:
            flash("Breed not found.", "error")
            return redirect(url_for('pets.species_index'))
    else:
        breed = Breed(species_id=species_id)

    # Basic fields
    breed.name = request.form['name']
    breed.summary = request.form['summary']
    breed.temperament = request.form.get('temperament')
    breed.exercise_needs = request.form.get('exercise_needs')
    breed.energy_level = request.form.get('energy_level', 'Medium')
    breed.grooming_needs = request.form.get('grooming_needs', 'Medium')
    breed.space_needs = request.form.get('space_needs', 'Medium')
    breed.trainability = request.form.get('trainability', 'Moderate')
    breed.care_level = request.form.get('care_level', 'Beginner')
    breed.lifespan = request.form.get('lifespan') or None
    breed.care_cost = request.form.get('care_cost') or None
    breed.allergy_friendly = request.form.get('allergy_friendly') == '1'

    # IMAGE UPLOAD
    file = request.files.get('image')
    if file and file.filename:
        filename = secure_filename(file.filename)
        path = f"uploads/breeds/{filename}"
        file.save(os.path.join(current_app.static_folder, path))
        breed.image_url = path
    elif not getattr(breed, 'image_url', None):
        breed.image_url = 'uploads/no-image-attachment.jpg'

    # Save breed
    db.session.add(breed)
    db.session.commit()

    # Update species breed count
    breed.species.update_breed_count()
    db.session.add(breed.species)
    db.session.commit()

    log_event('breed.saved', {'breed_id': breed.id, 'name': breed.name})
    flash(f"Breed {'updated' if breed_id else 'added'} successfully.", 'success')
    return redirect(url_for('pets.view_species', id=breed.species_id))



# -------------------
# DELETE BREED
# -------------------
@bp.route('/breed/<int:id>/delete', methods=['POST'])
@login_required
def delete_breed(id):
    breed = Breed.query.get_or_404(id)
    breed.soft_delete()

    # Update active breed count after soft delete
    breed.species.update_breed_count()
    db.session.add(breed.species)
    db.session.commit()
    flash("Breed deleted successfully.", "success")
    return redirect(url_for('pets.view_species', id=breed.species_id))

# -----------------------------
# VIEW ARCHIVED SPECIES & BREEDS
# -----------------------------
@bp.route('/archived')
@login_required
def archived_items():
    # Fetch soft-deleted species and breeds
    archived_species = Species.query.filter(Species.deleted_at.isnot(None)).order_by(Species.name.asc()).all()
    archived_breeds = Breed.query.filter(Breed.deleted_at.isnot(None)).order_by(Breed.name.asc()).all()

    # Calculate active breed counts for all species (active breeds only)
    breed_counts = dict(
        db.session.query(
            Breed.species_id,
            func.count(Breed.id)
        )
        .filter(Breed.deleted_at.is_(None))  # only active breeds
        .group_by(Breed.species_id)
        .all()
    )

    # Attach count to each archived species
    for species in archived_species:
        species.active_breeds_count = breed_counts.get(species.id, 0)

    # Optional: paginate active species (if needed)
    page = request.args.get('page', 1, type=int)
    pagination = Species.query.filter(Species.deleted_at.is_(None)).order_by(Species.name.asc()).paginate(
        page=page, per_page=8, error_out=False
    )
    species_list = pagination.items
    for species in species_list:
        species.active_breeds_count = breed_counts.get(species.id, 0)

    return render_template(
        'pets/archived_species.html',
        archived_species=archived_species,
        archived_breeds=archived_breeds,
        species_list=species_list,
        page_title="Archived Items"
    )

# -----------------------------
# RESTORE SPECIES
# -----------------------------
@bp.route('/species/<int:id>/restore', methods=['POST'])
@login_required
def restore_species(id):
    species = Species.query.get_or_404(id)
    species.deleted_at = None
    db.session.commit()

    log_event('species.restored', {'species_id': species.id, 'name': species.name})
    flash(f"Species '{species.name}' restored successfully.", 'success')
    return redirect(url_for('pets.archived_items'))

# -----------------------------
# RESTORE BREED
# -----------------------------
@bp.route('/breed/<int:id>/restore', methods=['POST'])
@login_required
def restore_breed(id):
    breed = Breed.query.get_or_404(id)
    breed.deleted_at = None
    breed.is_active = True
    db.session.commit()

    log_event('breed.restored', {'breed_id': breed.id, 'name': breed.name})
    flash(f"Breed '{breed.name}' restored successfully.", 'success')
    return redirect(url_for('pets.archived_items'))
