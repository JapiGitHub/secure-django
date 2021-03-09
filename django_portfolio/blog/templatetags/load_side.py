#lataa postaukset tagin kautta jotta voin käyttää niitä base.html:ssä. en voi ladata normaalisti views.py listview/classi kautta, koska
#ne on jo ladattu paginoituna versiona. 2 views in one url ei myöskään onnistu, eikä view classin sisään voi laittaa kuin yhden modelin.
from django import template
from ..models import Post

register = template.Library()

@register.simple_tag
def load_side_posts():
	return Post.objects.all()