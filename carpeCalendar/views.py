import datetime
import urllib.parse
import zoneinfo
from collections import defaultdict

import icalendar
from django.shortcuts import render, redirect, get_object_or_404
from django.forms.models import model_to_dict
from django.http import JsonResponse, HttpResponse
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

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
    subscribe_url = 'webcal://' + request.get_host() + reverse('calendar_ics')
    return render(request, 'calendar.html', {'category_tree': category_tree(), 'places': places, 'periods': periods, 'subscribe_url': subscribe_url})

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

def ics_event(request, date):
    event = date.event
    url = request.build_absolute_uri(reverse('event', args=[event.id]))
    ics = icalendar.Event()
    ics.add('uid', f"eventdate-{date.id}@agenda.carpestudentem.be")
    ics.add('dtstamp', event.updated_at)
    ics.add('dtstart', date.start)
    ics.add('dtend', date.end)
    ics.add('summary', event.title)
    ics.add('location', event.location)
    ics.add('description', f"{event.description}\n\n{url}" if event.description else url)
    ics.add('url', url)
    ics.add('categories', [event.category.name])
    return ics

def ics_response(request, dates, filename):
    calendar = icalendar.Calendar()
    calendar.add('prodid', '-//CarpeStudentem//Agenda du Carpe//FR')
    calendar.add('version', '2.0')
    calendar.add('x-wr-calname', 'Agenda du Carpe')
    calendar.add('x-wr-timezone', 'Europe/Brussels')
    # Ask subscribed calendar apps to refresh every 6 hours
    calendar.add('refresh-interval', datetime.timedelta(hours=6), parameters={'VALUE': 'DURATION'})
    calendar.add('x-published-ttl', 'PT6H')
    for date in dates:
        calendar.add_component(ics_event(request, date))
    response = HttpResponse(calendar.to_ical(), content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

def calendar_ics(request):
    # Subscription feed: from a month ago to a year ahead
    now = timezone.now()
    dates = EventDates.objects.filter(
        event__validated=True,
        end__gte=now - datetime.timedelta(days=30),
        start__lte=now + datetime.timedelta(days=365),
    ).select_related('event', 'event__category').order_by('start')
    return ics_response(request, dates, 'agenda-carpe.ics')

def event_ics(request, event_id):
    event = get_object_or_404(Event, id=event_id, validated=True)
    dates = event.eventdates_set.select_related('event', 'event__category').order_by('start')
    return ics_response(request, dates, f'evenement-{event.id}.ics')

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