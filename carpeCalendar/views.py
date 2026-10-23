import datetime
import urllib.parse
import zoneinfo
from collections import defaultdict

from django.shortcuts import render, redirect
from django.forms.models import model_to_dict
from django.http import JsonResponse
from django.db.models import Q

from carpeCalendar.models import Event, EventDates, Category, Place, AcademicPeriod
from carpeCalendar.forms import EventForm, DateForm

def home(request):
    return redirect('calendar')

def category_tree():
    # Categories as (category, children) pairs, with children nested the same way
    children = defaultdict(list)
    for category in Category.objects.order_by('name'):
        children[category.parent_id].append(category)
    seen = set()

    def build(parent_id):
        tree = []
        for category in children[parent_id]:
            # Guard against a category set as its own ancestor in the admin
            if category.id not in seen:
                seen.add(category.id)
                tree.append((category, build(category.id)))
        return tree

    return build(None)

def category_choices(tree=None, depth=0):
    # Flattened tree for a <select>, children indented under their parent
    choices = []
    for category, children in (category_tree() if tree is None else tree):
        choices.append((category.id, "\u00a0\u00a0\u00a0" * depth + ("↳ " if depth else "") + category.name))
        choices += category_choices(children, depth + 1)
    return choices

def calendar(request):
    places = Place.objects.all()
    periods = list(AcademicPeriod.objects.values('name', 'start', 'end', 'numbered', 'first_week_number'))
    return render(request, 'calendar.html', {'category_tree': category_tree(), 'places': places, 'periods': periods})

def events(request):
    start = request.GET.get('start', None)
    end = request.GET.get('end', None)
    end_dt = datetime.datetime.strptime(end, '%Y-%m-%dT%H:%M:%S%z')
    start_dt = datetime.datetime.strptime(start, '%Y-%m-%dT%H:%M:%S%z')
    if (end_dt - start_dt).days > 90:
        return JsonResponse([], safe=False)
    dates_lst = list(EventDates.objects.filter(Q(Q(start__range=[start, end]) | Q(end__range=[start, end]) | Q(start__lte=start, end__gte=end)), event__validated=True).select_related('event', 'event__category', 'event__saved_location'))
    events_lst = []
    for date in dates_lst:
        events_lst.append(model_to_dict(date.event) | {'start': date.start, 'end': date.end, 'category': model_to_dict(date.event.category), 'saved_location': model_to_dict(date.event.saved_location) if date.event.saved_location else {'name': 'Autre'}})
    return JsonResponse(events_lst, safe=False)

def event(request, event_id):
    event = Event.objects.get(id=event_id)
    if event.validated == False:
        return render(request, 'event.html', {'status': 403})
    dates = EventDates.objects.filter(event=event)
    return render(request, 'event.html', {'event': event, 'dates': dates, 'map_url': map_url(event)})

def map_url(event):
    # Google Maps search links open the maps app on phones
    place = event.saved_location
    if place and place.latitude is not None and place.longitude is not None:
        query = f"{place.latitude},{place.longitude}"
    elif place and place.address:
        query = place.address
    else:
        query = f"{event.location}, Louvain-la-Neuve"
    return "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(query)

def create_qr_code(request):
    return render(request, 'create_qr_code.html')

def add_event_page(request):
    categories = category_choices()
    places = list(Place.objects.exclude(name='Autre').values_list('name', flat=True))
    if request.method == 'POST':
        data = request.POST
        starts = data.getlist('start')
        ends = data.getlist('end')
        form = EventForm(data)
        if not form.is_valid():
            return render(request, 'add_event.html', {'status': 'error', 'messages': form.errors, 'categories': categories, 'places': places, "initial": data, "dates": list(zip(starts, ends)) or [("", "")]})
        try:
            location = form.cleaned_data['location']
            event = Event(
                title=form.cleaned_data['title'],
                description=form.cleaned_data['description'],
                organizer=form.cleaned_data['organizer'],
                location=form.cleaned_data['location'],
                category=form.cleaned_data['category'],
                facebook_link=form.cleaned_data["facebook_link"],
                email_organizer=form.cleaned_data["email_organizer"],
                form_link=form.cleaned_data["form_link"],
                pmr_friendly=form.cleaned_data["pmr_friendly"],
                deaf_friendly=form.cleaned_data["deaf_friendly"],
                blind_friendly=form.cleaned_data["blind_friendly"],
                neurodiversity_friendly=form.cleaned_data["neurodiversity_friendly"],
                granz_filled=form.cleaned_data["granz_filled"],
            )
            event.saved_location = Place.objects.get(name__iexact=location) if Place.objects.filter(name__iexact=location).exists() else Place.objects.get(name='Autre')
            event.save()
            for start_time, end_time in zip(starts, ends):
                start_datetime = datetime.datetime.strptime(start_time, '%Y-%m-%dT%H:%M').replace(tzinfo=zoneinfo.ZoneInfo('Europe/Brussels'))
                end_datetime = datetime.datetime.strptime(end_time, '%Y-%m-%dT%H:%M').replace(tzinfo=zoneinfo.ZoneInfo('Europe/Brussels'))
                date = EventDates(event=event, start=start_datetime, end=end_datetime)
                date.save()


        except Exception as e:
            print(e)
            return render(request, 'add_event.html', {'status': 'error', 'categories': categories, 'places': places, "initial": data, "dates": list(zip(starts, ends)) or [("", "")]})
        return render(request, 'add_event.html', {'status': 'success', 'categories': categories, 'places': places, 'dates': [('', '')], **model_to_dict(event)})

    form = EventForm()
    date_form = DateForm()
    return render(request, 'add_event.html', {'categories': categories, 'places': places, 'form': form, 'date_form': date_form, 'dates': [('', '')]})