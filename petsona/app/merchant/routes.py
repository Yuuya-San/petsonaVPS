from flask import render_template, flash, redirect, request, url_for
from flask_login import login_required, current_user # pyright: ignore[reportMissingImports]
from app.merchant import bp
from app.decorators import merchant_required
from app.models.breed import Breed
from app.models.species import Species

@bp.route('/dashboard')
@login_required
@merchant_required
def dashboard():
    if current_user.role != 'merchant':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.login'))

    return render_template('merchant/dashboard.html')



@bp.route('/species')
@login_required
@merchant_required
def species_index():
    page = request.args.get('page', 1, type=int)

    # Paginate active species
    pagination = Species.query.filter(
        Species.deleted_at.is_(None)
    ).order_by(Species.name.asc()).paginate(
        page=page, per_page=1000, error_out=False
    )

    species_list = pagination.items

    return render_template(
        'merchant/species_index.html',
        species_list=species_list,
        pagination=pagination,
        page_title="Pet Species"
    )

@bp.route('/species/<int:id>')
@login_required
@merchant_required
def view_species(id):
    species = Species.query.get_or_404(id)

    # Only fetch active breeds (not soft-deleted)
    breeds = Breed.query.filter_by(
        species_id=species.id,
        is_active=True   
    ).order_by(Breed.name.asc()).all()

    return render_template(
        'merchant/view_species.html',
        species=species,
        breeds=breeds,
        page_title=f"{species.name} Breeds"
    )
