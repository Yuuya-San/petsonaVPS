from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from ..models import Breed, Species, db
from ..utils.audit import log_event
from app.pets import bp

# ----------------------
# Add Species
# ----------------------
@bp.route('/species/add', methods=['GET', 'POST'])
@login_required
def add_species():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description')
        legal_status = request.form.get('legal_status')

        if not name or not legal_status:
            flash('All required fields must be filled.', 'danger')
            return redirect(request.url)

        species = Species(
            name=name,
            description=description,
            legal_status=legal_status
        )
        db.session.add(species)
        db.session.commit()

        log_event(
            event='species.add',
            details={
                'species_id': species.id,
                'name': name,
                'description': description,
                'legal_status': legal_status
            }
        )

        flash('Species added successfully.', 'success')
        return redirect(url_for('pets.all_pets'))

    return render_template('pets/add_species.html')

# ----------------------
# Add Breed
# ----------------------
@bp.route('/breed/add', methods=['GET', 'POST'])
@login_required
def add_breed():
    species_list = Species.query.all()

    if request.method == 'POST':
        breed = Breed(
            species_id=request.form.get('species_id'),
            name=request.form.get('name'),
            summary=request.form.get('summary'),
            temperament=request.form.get('temperament'),
            energy_level=request.form.get('energy_level'),
            exercise_needs=request.form.get('exercise_needs'),
            grooming_needs=request.form.get('grooming_needs'),
            space_needs=request.form.get('space_needs'),
            trainability=request.form.get('trainability'),
            health_issues=request.form.get('health_issues'),
            lifespan=request.form.get('lifespan', type=int),
            care_cost=request.form.get('care_cost', type=float),
            personality_traits=request.form.get('personality_traits').split(','),
            allergy_friendly=bool(request.form.get('allergy_friendly')),
            image_url=request.form.get('image_url')
        )

        db.session.add(breed)
        db.session.commit()

        log_event(
            event='breed.add',
            details={
                'breed_id': breed.id,
                'name': breed.name,
                'species_id': breed.species_id,
                'energy_level': breed.energy_level,
                'space_needs': breed.space_needs,
                'care_cost': breed.care_cost,
                'traits': breed.personality_traits
            }
        )

        flash('Breed added successfully.', 'success')
        return redirect(url_for('pets.all_pets'))

    return render_template(
        'pets/add_breed.html',
        species_list=species_list
    )

# ----------------------
# All Pets
# ----------------------
@bp.route('/')
@login_required
def all_pets():
    species_list = Species.query.all()
    breeds = Breed.query.all()

    log_event(
        event='pets.view_all',
        details={
            'species_count': len(species_list),
            'breed_count': len(breeds)
        }
    )

    return render_template(
        'pets/all_pets.html',
        species_list=species_list
    )
