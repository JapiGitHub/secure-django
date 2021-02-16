from django.contrib import admin
from .models import Profile

#jotta profiilit näkyy admin sivulla, ne pitää rekisteröidä tähän
admin.site.register(Profile)
