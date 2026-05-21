import os
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import (
    render_template, request, redirect,
    url_for, flash, abort, current_app
)
from flask_login import login_required, current_user # pyright: ignore[reportMissingImports]

from app import db
from app.models import Species, Breed
from app.utils.audit import log_event, log_action_with_changes
from . import bp
from sqlalchemy import func, or_ # pyright: ignore[reportMissingImports]
from app.decorators import admin_required, user_required, merchant_required
import pytz

# Philippine timezone helper
PH_TZ = pytz.timezone('Asia/Manila')

def get_ph_datetime():
    """Get current datetime in Philippine timezone"""
    return datetime.now(PH_TZ)



@bp.route('/species')
@login_required
@admin_required
def species_index():
    page = request.args.get('page', 1, type=int)

    # Paginate active species
    pagination = Species.query.filter(
        Species.deleted_at.is_(None)
    ).order_by(Species.name.asc()).paginate(
        page=page, per_page=1000, error_out=False
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
    

    return render_template(
        'pets/species_index.html',
        species_list=species_list,
        pagination=pagination,
        page_title="Pet Species"
    )


@bp.route('/species/save', methods=['POST'])
@login_required
@admin_required
def save_species():
    species_id = request.form.get('species_id')
    is_update = bool(species_id)  # Track if this is an edit or create

    if is_update:
        species = Species.query.get_or_404(species_id)
    else:
        species = Species()

    # Check for duplicate species name
    species_name = request.form.get("name", "").strip()
    
    # Query for existing species with this name (excluding soft-deleted)
    existing_species = Species.query.filter(
        Species.name.ilike(species_name),
        Species.deleted_at.is_(None)
    ).first()
    
    # If there's an existing species and it's not the one we're updating
    if existing_species and (not is_update or existing_species.id != species.id):
        flash(f"A species with the name '{species_name}' already exists.", "warning")
        return redirect(url_for('pets.species_index'))

    # Track changes for audit log
    changes = {}

    # Helper function to track individual field changes
    def track_change(field_name, new_value):
        old_value = getattr(species, field_name, None)
        if old_value != new_value:
            changes[field_name] = {"old": old_value, "new": new_value}
            setattr(species, field_name, new_value)

    # ---- BASIC FIELDS ----
    track_change("name", request.form.get("name", "").strip())
    track_change("description", request.form.get("description", "").strip())
    track_change("icon", request.form.get("icon", "").strip())

    # ---- BOOLEAN FIELDS ----
    boolean_fields = [
        "requires_exercise",
        "requires_training",
        "requires_grooming",
        "requires_enclosure",
        "predatory_species",
        "fragile_species",
        "beginner_friendly",
        "requires_permit",
        "special_vet_required",
        "has_breed"
    ]

    for field in boolean_fields:
        value = bool(request.form.get(field))  # Checked → True, Unchecked → False
        track_change(field, value)

    # ---- ENUMERATION FIELDS ----
    abandonment_risk = request.form.get("abandonment_risk_level", "Medium").strip()
    if abandonment_risk in ["Low", "Medium", "High"]:
        track_change("abandonment_risk_level", abandonment_risk)

    # ---- TEXT FIELDS ----
    track_change("ethical_notes", request.form.get("ethical_notes", "").strip())

    # ---- IMAGE HANDLING ----
    file = request.files.get("image")
    if file and file.filename:
        filename = secure_filename(file.filename)
        path = f"uploads/species/{filename}"
        file.save(os.path.join(current_app.static_folder, path))
        if species.image_url != path:
            changes["image_url"] = {"old": species.image_url, "new": path}
            species.image_url = path
    elif not species.image_url:
        species.image_url = "uploads/no-image-attachment.jpg"

    # ---- SAVE ----
    db.session.add(species)
    db.session.commit()

    # ---- AUDIT LOG ----
    if changes or not is_update:
        log_action_with_changes(
            event_name=f"species.{'updated' if is_update else 'created'}",
            entity_id=species.id,
            old_values={k: v["old"] for k, v in changes.items()},
            new_values={k: v["new"] for k, v in changes.items()},
            entity_type='species',
            metadata={'species_name': species.name, 'is_update': is_update}
        )

    flash(f"Species {'updated' if is_update else 'added'} successfully.", "success")
    return redirect(url_for("pets.species_index"))


@bp.route('/species/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_species(id):
    species = Species.query.get_or_404(id)
    species.deleted_at = get_ph_datetime()
    db.session.commit()

    log_action_with_changes(
        event_name='species.deleted',
        entity_id=species.id,
        entity_type='species',
        metadata={'species_name': species.name, 'soft_delete': True}
    )

    flash('Species deleted.', 'warning')
    return redirect(url_for('pets.species_index'))

@bp.route('/species/<int:id>')
@login_required
@admin_required
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
@admin_required
def save_breed():
    breed_id = request.form.get('breed_id')
    species_id = request.form.get('species_id')

    if breed_id:
        breed = Breed.query.get(breed_id)
        if not breed:
            flash("Breed not found.", "error")
            return redirect(url_for('pets.species_index'))
        is_update = True
    else:
        breed = Breed(species_id=species_id)
        is_update = False

    changes = {}

    def track_change(field_name, new_value):
        old_value = getattr(breed, field_name, None)
        if old_value != new_value:
            changes[field_name] = {"old": old_value, "new": new_value}
            setattr(breed, field_name, new_value)

    # --- TEXT FIELDS ---
    track_change("name", request.form.get('name'))
    track_change("summary", request.form.get('summary'))
    track_change("temperament", request.form.get('temperament'))
    
    # --- SELECT FIELDS ---
    track_change("energy_level", request.form.get('energy_level', 'Medium'))
    track_change("exercise_needs", request.form.get('exercise_needs', 'Medium'))
    track_change("grooming_needs", request.form.get('grooming_needs', 'Medium'))
    track_change("space_needs", request.form.get('space_needs', 'Medium'))
    track_change("size_category", request.form.get('size_category') or None)
    track_change("trainability", request.form.get('trainability', 'Moderate'))
    track_change("care_level", request.form.get('care_level', 'Beginner'))
    track_change("care_intensity", request.form.get('care_intensity', 'Medium'))
    track_change("time_commitment", request.form.get('time_commitment', 'Medium'))
    track_change("experience_required", request.form.get('experience_required', 'Beginner'))
    track_change("environment_complexity", request.form.get('environment_complexity', 'Simple'))
    track_change("handling_tolerance", request.form.get('handling_tolerance', 'Medium'))
    track_change("noise_level", request.form.get('noise_level', 'Low'))
    track_change("social_needs", request.form.get('social_needs', 'Medium'))
    track_change("compatibility_risk", request.form.get('compatibility_risk', 'Low'))
    track_change("prey_drive", request.form.get('prey_drive', 'None'))

    # --- TEXT FIELDS (FORMERLY NUMERIC) ---
    lifespan_val = request.form.get('lifespan', '').strip() if request.form.get('lifespan') else None
    track_change("lifespan", lifespan_val)

    care_cost_val = request.form.get('care_cost', '').strip() if request.form.get('care_cost') else None
    track_change("care_cost", care_cost_val)

    # --- CHECKBOXES ---
    track_change("allergy_friendly", bool(request.form.get('allergy_friendly')))
    track_change("dog_friendly", bool(request.form.get('dog_friendly')))
    track_change("cat_friendly", bool(request.form.get('cat_friendly')))
    track_change("small_pet_friendly", bool(request.form.get('small_pet_friendly')))
    track_change("child_friendly", bool(request.form.get('child_friendly')))
    track_change("senior_friendly", bool(request.form.get('senior_friendly')))

    # --- TEXT FIELDS ---
    min_enclosure_val = request.form.get('min_enclosure_size', '').strip() if request.form.get('min_enclosure_size') else None
    track_change("min_enclosure_size", min_enclosure_val)

    # --- ADDITIONAL SELECT FIELDS ---
    track_change("preventive_care_level", request.form.get('preventive_care_level', 'Medium'))
    track_change("emergency_care_risk", request.form.get('emergency_care_risk', 'Low'))
    track_change("stress_sensitivity", request.form.get('stress_sensitivity', 'Medium'))
    track_change("monthly_cost_level", request.form.get('monthly_cost_level', 'Medium'))
    track_change("lifetime_cost_level", request.form.get('lifetime_cost_level', 'Medium'))

    # --- TEXT AREA FIELDS ---
    common_health = request.form.get('common_health_issues', '').strip() if request.form.get('common_health_issues') else None
    track_change("common_health_issues", common_health)

    healthcare = request.form.get('healthcare_info', '').strip() if request.form.get('healthcare_info') else None
    track_change("healthcare_info", healthcare)

    # --- IMAGE UPLOAD ---
    file = request.files.get('image')
    if file and file.filename:
        filename = secure_filename(file.filename)
        path = f"uploads/breeds/{filename}"
        file.save(os.path.join(current_app.static_folder, path))
        if breed.image_url != path:
            changes['image_url'] = {"old": breed.image_url, "new": path}
            breed.image_url = path
    elif not getattr(breed, 'image_url', None):
        breed.image_url = 'uploads/no-image-attachment.jpg'

    # --- SAVE ---
    db.session.add(breed)
    db.session.commit()

    # Update species breed count
    if hasattr(breed, 'species') and hasattr(breed.species, 'update_breed_count'):
        breed.species.update_breed_count()
        db.session.add(breed.species)
        db.session.commit()

    # --- AUDIT LOG ---
    if changes or not is_update:
        log_action_with_changes(
            event_name=f"breed.{'updated' if is_update else 'created'}",
            entity_id=breed.id,
            old_values={k: v["old"] for k, v in changes.items()},
            new_values={k: v["new"] for k, v in changes.items()},
            entity_type='breed',
            metadata={
                'breed_name': breed.name,
                'species_id': breed.species_id,
                'is_update': is_update
            }
        )

    # Build success message
    change_count = len(changes) if changes else 0
    if change_count > 0:
        flash(f"Breed {'updated' if is_update else 'added'} successfully. {change_count} field(s) saved.", 'success')
    else:
        flash(f"Breed {'updated' if is_update else 'added'} successfully.", 'success')
    return redirect(url_for('pets.view_species', id=breed.species_id))


# -------------------
# DELETE BREED
# -------------------
@bp.route('/breed/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_breed(id):
    breed = Breed.query.get_or_404(id)
    species_id = breed.species_id
    
    log_action_with_changes(
        event_name='breed.deleted',
        entity_id=breed.id,
        entity_type='breed',
        metadata={'breed_name': breed.name, 'species_id': species_id, 'soft_delete': True}
    )
    
    breed.soft_delete()

    # Update active breed count after soft delete
    breed.species.update_breed_count()
    db.session.add(breed.species)
    db.session.commit()
    flash("Breed deleted successfully.", "success")
    return redirect(url_for('pets.view_species', id=species_id))

# -----------------------------
# VIEW ARCHIVED SPECIES & BREEDS
# -----------------------------
@bp.route('/archived')
@login_required
@admin_required
def archived_items():
    search = request.args.get('search', '', type=str).strip()

    # Fetch soft-deleted species and breeds
    archived_species_q = Species.query.filter(Species.deleted_at.isnot(None))
    archived_breeds_q = Breed.query.filter(Breed.deleted_at.isnot(None))

    if search:
        search_term = f"%{search}%"
        archived_species_q = archived_species_q.filter(
            or_(
                Species.name.ilike(search_term),
                Species.description.ilike(search_term)
            )
        )
        archived_breeds_q = archived_breeds_q.filter(
            or_(
                Breed.name.ilike(search_term),
                Breed.summary.ilike(search_term),
                Breed.preventive_care_level.ilike(search_term),
                Breed.species.has(Species.name.ilike(search_term))
            )
        )

    archived_species = archived_species_q.order_by(Species.name.asc()).all()
    archived_breeds = archived_breeds_q.order_by(Breed.name.asc()).all()

    archived_items = []
    for species in archived_species:
        archived_items.append({
            'id': species.id,
            'name': species.name,
            'type': 'species',
            'type_label': 'Species',
            'species_name': '—',
            'deleted_at': species.deleted_at,
            'details': species.description or '',
            'action_url': url_for('pets.restore_species', id=species.id),
        })

    for breed in archived_breeds:
        archived_items.append({
            'id': breed.id,
            'name': breed.name,
            'type': 'breed',
            'type_label': 'Breed',
            'species_name': breed.species.name if breed.species else '—',
            'deleted_at': breed.deleted_at,
            'details': breed.summary or '',
            'care_level': breed.preventive_care_level or '',
            'action_url': url_for('pets.restore_breed', id=breed.id),
        })

    archived_items.sort(key=lambda item: (item['name'] or '').lower())

    page = request.args.get('page', 1, type=int)
    per_page = 10
    total_items = len(archived_items)
    total_pages = max(1, (total_items + per_page - 1) // per_page)
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages

    start = (page - 1) * per_page
    end = start + per_page
    paged_items = archived_items[start:end]

    pagination = {
        'page': page,
        'per_page': per_page,
        'total': total_items,
        'pages': total_pages,
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'prev_num': page - 1 if page > 1 else 1,
        'next_num': page + 1 if page < total_pages else total_pages,
    }

    return render_template(
        'pets/archived_species.html',
        archived_items=paged_items,
        pagination=pagination,
        page_title="Archived Items",
        search=search
    )

# -----------------------------
# RESTORE SPECIES
# -----------------------------
@bp.route('/species/<int:id>/restore', methods=['POST'])
@login_required
@admin_required
def restore_species(id):
    species = Species.query.get_or_404(id)
    species.deleted_at = None
    db.session.commit()

    log_action_with_changes(
        event_name='species.restored',
        entity_id=species.id,
        entity_type='species',
        metadata={'species_name': species.name, 'restore_action': True}
    )
    flash(f"Species '{species.name}' restored successfully.", 'success')
    return redirect(url_for('pets.archived_items'))

# -----------------------------
# RESTORE BREED
# -----------------------------
@bp.route('/breed/<int:id>/restore', methods=['POST'])
@login_required
@admin_required
def restore_breed(id):
    breed = Breed.query.get_or_404(id)
    breed.deleted_at = None
    breed.is_active = True
    db.session.commit()

    log_action_with_changes(
        event_name='breed.restored',
        entity_id=breed.id,
        entity_type='breed',
        metadata={'breed_name': breed.name, 'species_id': breed.species_id, 'restore_action': True}
    )
    flash(f"Breed '{breed.name}' restored successfully.", 'success')
    return redirect(url_for('pets.archived_items'))
