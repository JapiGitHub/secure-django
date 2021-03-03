from django import template
from ..models import Post

register = template.Library()

@register.simple_tag
def load_side_posts():
	return Post.objects.all()