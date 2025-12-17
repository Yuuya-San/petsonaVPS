"""Profile forms for editing user information and avatar."""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, Optional
import os

# Default avatars available for selection
DEFAULT_AVATARS = [
    "images/avatar/cat.png",
    "images/avatar/dog.png",
    "images/avatar/frog-.png",
    "images/avatar/hamster.png",
    "images/avatar/penguin.png",
    "images/avatar/puffer-fish.png",
    "images/avatar/rabbit.png",
    "images/avatar/snake.png"
]


class ProfileForm(FlaskForm):
    """Form for editing user profile information."""
    
    first_name = StringField(
        'First Name',
        validators=[
            DataRequired(message='First name is required'),
            Length(min=2, max=64, message='First name must be between 2 and 64 characters')
        ]
    )
    
    last_name = StringField(
        'Last Name',
        validators=[
            DataRequired(message='Last name is required'),
            Length(min=2, max=64, message='Last name must be between 2 and 64 characters')
        ]
    )
    
    # Avatar selection: either upload new or choose from existing
    avatar_choice = SelectField(
        'Choose Default Avatar',
        choices=[(avatar, avatar.split('/')[-1].replace('.png', '').title()) for avatar in DEFAULT_AVATARS],
        validators=[Optional()]
    )
    
    # File upload for custom avatar
    avatar_upload = FileField(
        'Or Upload Custom Avatar',
        validators=[
            FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Images only (jpg, jpeg, png, gif)')
        ]
    )
    
    submit = SubmitField('Save Profile')
