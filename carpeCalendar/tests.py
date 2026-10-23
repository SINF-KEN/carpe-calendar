import datetime
import zoneinfo
from unittest import mock

import icalendar

from django.test import TestCase

from carpeCalendar.models import Event, EventDates, Category, Place

BRUSSELS = zoneinfo.ZoneInfo('Europe/Brussels')


class SmokeTests(TestCase):
    # Quick end-to-end checks of every page, so dependency updates can be validated in CI

    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name='Soirée', description='')
        cls.other_place = Place.objects.create(name='Autre')
        cls.place = Place.objects.create(name='Grand-Place')
        cls.event = Event.objects.create(title='Validated event', location='Grand-Place', saved_location=cls.place, category=cls.category, validated=True)
        EventDates.objects.create(
            event=cls.event,
            start=datetime.datetime(2026, 10, 22, 20, 0, tzinfo=BRUSSELS),
            end=datetime.datetime(2026, 10, 22, 23, 0, tzinfo=BRUSSELS),
        )
        hidden = Event.objects.create(title='Pending event', location='Grand-Place', saved_location=cls.place, category=cls.category)
        EventDates.objects.create(
            event=hidden,
            start=datetime.datetime(2026, 10, 23, 20, 0, tzinfo=BRUSSELS),
            end=datetime.datetime(2026, 10, 23, 23, 0, tzinfo=BRUSSELS),
        )

    def test_calendar_page(self):
        response = self.client.get('/calendar/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Soirée')

    def test_events_only_returns_validated(self):
        response = self.client.get('/events/', {'start': '2026-10-19T00:00:00+02:00', 'end': '2026-10-26T00:00:00+01:00'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([event['title'] for event in response.json()], ['Validated event'])

    def test_events_without_saved_location(self):
        self.event.saved_location = None
        self.event.save()
        response = self.client.get('/events/', {'start': '2026-10-19T00:00:00+02:00', 'end': '2026-10-26T00:00:00+01:00'})
        self.assertEqual(response.json()[0]['saved_location'], {'name': 'Autre'})

    def test_event_page(self):
        response = self.client.get(f'/event/{self.event.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Validated event')

    def test_add_event_creates_pending_event(self):
        self.assertEqual(self.client.get('/add-event').status_code, 200)
        response = self.client.post('/add-event', {
            'title': 'New event',
            'organizer': 'Carpe',
            'location': 'Somewhere else',
            'category': self.category.id,
            'start': '2026-11-02T20:00',
            'end': '2026-11-02T23:00',
        })
        self.assertContains(response, 'alert-success')
        event = Event.objects.get(title='New event')
        self.assertFalse(event.validated)
        self.assertEqual(event.saved_location, self.other_place)
        self.assertEqual(event.eventdates_set.count(), 1)

    def test_qr_code_page(self):
        self.assertEqual(self.client.get('/create-qr-code').status_code, 200)

    def test_admin_login_page(self):
        self.assertEqual(self.client.get('/admin/login/').status_code, 200)


class CategoryTreeTests(TestCase):

    def test_subcategories_are_nested_in_filters_and_form(self):
        sport = Category.objects.create(name='Sport', description='')
        Category.objects.create(name='Football', parent=sport, description='')
        Category.objects.create(name='Concert', description='')

        response = self.client.get('/calendar/')
        tree = [(category.name, [child.name for child, _ in children]) for category, children in response.context['category_tree']]
        self.assertEqual(tree, [('Concert', []), ('Sport', ['Football'])])

        response = self.client.get('/add-event')
        labels = [label for _, label in response.context['categories']]
        self.assertEqual(labels, ['Concert', 'Sport', '\u00a0\u00a0\u00a0↳ Football'])


class IcsTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        category = Category.objects.create(name='Soirée', description='')
        cls.event = Event.objects.create(title='Concert, jazz', location='Aula Magna', category=category, validated=True)
        cls.date = EventDates.objects.create(
            event=cls.event,
            start=datetime.datetime(2026, 11, 2, 20, 0, tzinfo=BRUSSELS),
            end=datetime.datetime(2026, 11, 2, 23, 0, tzinfo=BRUSSELS),
        )
        Event.objects.create(title='Pending', location='Aula Magna', category=category)

    def test_event_ics(self):
        response = self.client.get(f'/event/{self.event.id}/ics')
        self.assertEqual(response['Content-Type'], 'text/calendar; charset=utf-8')
        calendar = icalendar.Calendar.from_ical(response.content)
        [event] = calendar.walk('VEVENT')
        self.assertEqual(str(event['summary']), 'Concert, jazz')
        self.assertEqual(event.decoded('dtstart'), self.date.start)
        self.assertIn(f'/event/{self.event.id}/', str(event['url']))

    def test_pending_event_ics_is_not_found(self):
        pending = Event.objects.get(title='Pending')
        self.assertEqual(self.client.get(f'/event/{pending.id}/ics').status_code, 404)

    @mock.patch('django.utils.timezone.now', return_value=datetime.datetime(2026, 10, 24, tzinfo=datetime.UTC))
    def test_calendar_feed(self, _):
        response = self.client.get('/calendar.ics')
        calendar = icalendar.Calendar.from_ical(response.content)
        self.assertEqual([str(event['summary']) for event in calendar.walk('VEVENT')], ['Concert, jazz'])
