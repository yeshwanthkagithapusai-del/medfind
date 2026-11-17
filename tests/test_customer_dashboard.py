from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from medicines.models import Medicine
from pharmacies.models import Pharmacy
from requests_app.models import AvailabilityRequest, Notification

User = get_user_model()


class CustomerDashboardAndTrackingTests(TestCase):
    """
    Automated test suite verifying the 13 vectors required for Phase 5:
    1. Customer dashboard access.
    2. Anonymous user restrictions.
    3. Dashboard statistics accuracy.
    4. Customer request history.
    5. Request filtering.
    6. Request pagination.
    7. Request ownership and isolation.
    8. Request cancellation permissions.
    9. Notification listing.
    10. Mark notification as read.
    11. Notification ownership and isolation.
    12. Dashboard query correctness and tenant isolation.
    13. Mark all notifications as read.
    """

    def setUp(self):
        self.client = Client()

        # Primary Customer A
        self.customer_a = User.objects.create_user(
            username='alice_patient',
            email='alice@example.com',
            password='PatientPass123!',
            first_name='Alice',
            last_name='Wonder',
            phone_number='9876543210',
            role='CUSTOMER'
        )

        # Secondary Customer B (for isolation tests)
        self.customer_b = User.objects.create_user(
            username='bob_patient',
            email='bob@example.com',
            password='PatientPass123!',
            first_name='Bob',
            last_name='Builder',
            phone_number='9876543211',
            role='CUSTOMER'
        )

        # Pharmacy Owner User & Pharmacy
        self.pharmacy_owner = User.objects.create_user(
            username='pharm_chemist',
            email='chemist@carepharma.com',
            password='ChemistPass123!',
            role='PHARMACY'
        )
        self.pharmacy = Pharmacy.objects.create(
            owner=self.pharmacy_owner,
            pharmacy_name="CarePlus Pharmacy",
            registration_number="REG-CARE-100",
            address="12 Banjara Hills",
            city="Hyderabad",
            state="Telangana",
            pincode="500034",
            phone_number="040-23344556",
            is_approved=True
        )

        # Master Medicines
        self.med_dolo = Medicine.objects.create(
            medicine_name="Dolo 650",
            generic_name="Paracetamol",
            category="Analgesics & Pain Relief",
            dosage_form="Tablet",
            strength="650mg"
        )
        self.med_cetirizine = Medicine.objects.create(
            medicine_name="Cetirizine 10mg",
            generic_name="Cetirizine HCl",
            category="Antihistamines",
            dosage_form="Tablet",
            strength="10mg"
        )

    # 1. Customer dashboard access
    def test_customer_dashboard_access(self):
        self.client.force_login(self.customer_a)
        resp = self.client.get(reverse('customer_dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Alice")
        self.assertContains(resp, "Patient Portal")
        self.assertIn('total_requests', resp.context)
        self.assertIn('pending_requests', resp.context)
        self.assertIn('confirmed_requests', resp.context)
        self.assertIn('unavailable_requests', resp.context)

    # 2. Anonymous user restrictions
    def test_anonymous_user_restrictions(self):
        resp = self.client.get(reverse('customer_dashboard'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/accounts/login/', resp.url)

    # 3. Dashboard statistics accuracy
    def test_dashboard_statistics(self):
        # Create known distribution for Customer A:
        # 2 Pending, 1 Confirmed, 1 Unavailable, 1 Cancelled
        AvailabilityRequest.objects.create(
            customer=self.customer_a, pharmacy=self.pharmacy, medicine=self.med_dolo,
            quantity_requested=2, status='PENDING'
        )
        AvailabilityRequest.objects.create(
            customer=self.customer_a, pharmacy=self.pharmacy, medicine=self.med_cetirizine,
            quantity_requested=1, status='PENDING'
        )
        AvailabilityRequest.objects.create(
            customer=self.customer_a, pharmacy=self.pharmacy, medicine=self.med_dolo,
            quantity_requested=3, status='CONFIRMED'
        )
        AvailabilityRequest.objects.create(
            customer=self.customer_a, pharmacy=self.pharmacy, medicine=self.med_cetirizine,
            quantity_requested=5, status='UNAVAILABLE'
        )
        AvailabilityRequest.objects.create(
            customer=self.customer_a, pharmacy=self.pharmacy, medicine=self.med_dolo,
            quantity_requested=1, status='CANCELLED'
        )

        self.client.force_login(self.customer_a)
        resp = self.client.get(reverse('customer_dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['total_requests'], 5)
        self.assertEqual(resp.context['pending_requests'], 2)
        self.assertEqual(resp.context['confirmed_requests'], 1)
        self.assertEqual(resp.context['unavailable_requests'], 1)
        self.assertEqual(resp.context['cancelled_requests'], 1)

    # 4. Customer request history
    def test_customer_request_history(self):
        req = AvailabilityRequest.objects.create(
            customer=self.customer_a, pharmacy=self.pharmacy, medicine=self.med_dolo,
            quantity_requested=4, status='PENDING', request_message="Need urgently"
        )
        self.client.force_login(self.customer_a)
        resp = self.client.get(reverse('customer_requests'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Dolo 650")
        self.assertContains(resp, "CarePlus Pharmacy")
        self.assertContains(resp, "<strong>4</strong> units")
        self.assertContains(resp, "Pending Pharmacy Review")

    # 5. Request filtering
    def test_request_filtering(self):
        AvailabilityRequest.objects.create(
            customer=self.customer_a, pharmacy=self.pharmacy, medicine=self.med_dolo,
            quantity_requested=2, status='PENDING'
        )
        AvailabilityRequest.objects.create(
            customer=self.customer_a, pharmacy=self.pharmacy, medicine=self.med_cetirizine,
            quantity_requested=1, status='CONFIRMED'
        )
        self.client.force_login(self.customer_a)

        # Filter PENDING
        resp_p = self.client.get(reverse('customer_requests'), {'status': 'PENDING'})
        self.assertEqual(resp_p.status_code, 200)
        self.assertEqual(len(resp_p.context['requests']), 1)
        self.assertEqual(resp_p.context['requests'][0].status, 'PENDING')

        # Filter CONFIRMED
        resp_c = self.client.get(reverse('customer_requests'), {'status': 'CONFIRMED'})
        self.assertEqual(resp_c.status_code, 200)
        self.assertEqual(len(resp_c.context['requests']), 1)
        self.assertEqual(resp_c.context['requests'][0].status, 'CONFIRMED')

    # 6. Request pagination
    def test_request_pagination(self):
        # Create 14 requests for customer A
        for i in range(14):
            AvailabilityRequest.objects.create(
                customer=self.customer_a, pharmacy=self.pharmacy, medicine=self.med_dolo,
                quantity_requested=i + 1, status='PENDING'
            )
        self.client.force_login(self.customer_a)

        # Page 1 should hold 10 requests
        resp_p1 = self.client.get(reverse('customer_requests'), {'page': '1'})
        self.assertEqual(resp_p1.status_code, 200)
        self.assertEqual(len(resp_p1.context['requests']), 10)
        self.assertTrue(resp_p1.context['page_obj'].has_next())

        # Page 2 should hold 4 requests
        resp_p2 = self.client.get(reverse('customer_requests'), {'page': '2'})
        self.assertEqual(resp_p2.status_code, 200)
        self.assertEqual(len(resp_p2.context['requests']), 4)
        self.assertFalse(resp_p2.context['page_obj'].has_next())

    # 7. Request ownership and tenant isolation
    def test_request_ownership(self):
        # Request for Customer B
        req_b = AvailabilityRequest.objects.create(
            customer=self.customer_b, pharmacy=self.pharmacy, medicine=self.med_cetirizine,
            quantity_requested=2, status='PENDING'
        )
        self.client.force_login(self.customer_a)

        # Customer A's dashboard must NOT include Customer B's request
        resp_dash = self.client.get(reverse('customer_dashboard'))
        self.assertEqual(resp_dash.context['total_requests'], 0)

        # Customer A's request list must NOT include Customer B's request
        resp_list = self.client.get(reverse('customer_requests'))
        self.assertEqual(len(resp_list.context['requests']), 0)
        self.assertNotContains(resp_list, f"#{req_b.id}")

    # 8. Request cancellation permissions
    def test_request_cancellation_permissions(self):
        # Customer A pending request -> can cancel
        req_pending = AvailabilityRequest.objects.create(
            customer=self.customer_a, pharmacy=self.pharmacy, medicine=self.med_dolo,
            quantity_requested=2, status='PENDING'
        )
        self.client.force_login(self.customer_a)
        resp_cancel = self.client.post(reverse('cancel_request', args=[req_pending.id]))
        self.assertEqual(resp_cancel.status_code, 302)
        req_pending.refresh_from_db()
        self.assertEqual(req_pending.status, 'CANCELLED')

        # Customer A confirmed request -> CANNOT cancel
        req_confirmed = AvailabilityRequest.objects.create(
            customer=self.customer_a, pharmacy=self.pharmacy, medicine=self.med_dolo,
            quantity_requested=2, status='CONFIRMED'
        )
        resp_cancel_conf = self.client.post(reverse('cancel_request', args=[req_confirmed.id]))
        self.assertEqual(resp_cancel_conf.status_code, 302)
        req_confirmed.refresh_from_db()
        self.assertEqual(req_confirmed.status, 'CONFIRMED')

        # Customer A cannot cancel Customer B's request (404 Not Found)
        req_b = AvailabilityRequest.objects.create(
            customer=self.customer_b, pharmacy=self.pharmacy, medicine=self.med_dolo,
            quantity_requested=1, status='PENDING'
        )
        resp_cancel_other = self.client.post(reverse('cancel_request', args=[req_b.id]))
        self.assertEqual(resp_cancel_other.status_code, 404)
        req_b.refresh_from_db()
        self.assertEqual(req_b.status, 'PENDING')

    # 9. Notification listing
    def test_notification_listing(self):
        Notification.objects.create(
            user=self.customer_a, message="Your inquiry for Dolo 650 is confirmed.", is_read=False
        )
        self.client.force_login(self.customer_a)
        resp = self.client.get(reverse('notifications'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Your inquiry for Dolo 650 is confirmed.")
        self.assertEqual(resp.context['unread_count'], 1)

    # 10. Mark notification as read
    def test_mark_notification_as_read(self):
        notif = Notification.objects.create(
            user=self.customer_a, message="Stock update notification", is_read=False
        )
        self.assertFalse(notif.is_read)
        self.client.force_login(self.customer_a)
        resp = self.client.post(reverse('mark_notification_read', args=[notif.id]))
        self.assertEqual(resp.status_code, 302)
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)

    # 11. Notification ownership and isolation
    def test_notification_ownership(self):
        notif_b = Notification.objects.create(
            user=self.customer_b, message="Bob's private alert", is_read=False
        )
        self.client.force_login(self.customer_a)

        # Customer A notification center does NOT show Customer B's alerts
        resp_list = self.client.get(reverse('notifications'))
        self.assertNotContains(resp_list, "Bob's private alert")

        # Customer A cannot mark Customer B's alert as read (404 Not Found)
        resp_mark = self.client.post(reverse('mark_notification_read', args=[notif_b.id]))
        self.assertEqual(resp_mark.status_code, 404)
        notif_b.refresh_from_db()
        self.assertFalse(notif_b.is_read)

    # 12. Dashboard query correctness
    def test_dashboard_query_correctness(self):
        # Populate records for Customer B
        AvailabilityRequest.objects.create(
            customer=self.customer_b, pharmacy=self.pharmacy, medicine=self.med_dolo,
            quantity_requested=10, status='PENDING'
        )
        Notification.objects.create(user=self.customer_b, message="Notice for Bob", is_read=False)

        # Check Customer A's dashboard is completely clean
        self.client.force_login(self.customer_a)
        resp = self.client.get(reverse('customer_dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['total_requests'], 0)
        self.assertEqual(resp.context['unread_notifications_count'], 0)
        self.assertEqual(len(resp.context['recent_requests']), 0)
        self.assertEqual(len(resp.context['recent_notifications']), 0)

    # 13. Mark all notifications as read
    def test_mark_all_notifications_read(self):
        Notification.objects.create(user=self.customer_a, message="Alert 1", is_read=False)
        Notification.objects.create(user=self.customer_a, message="Alert 2", is_read=False)
        Notification.objects.create(user=self.customer_b, message="Alert Bob", is_read=False)

        self.client.force_login(self.customer_a)
        resp = self.client.post(reverse('mark_all_notifications_read'))
        self.assertEqual(resp.status_code, 302)

        # Customer A's notifications are now read
        self.assertEqual(Notification.objects.filter(user=self.customer_a, is_read=False).count(), 0)
        # Customer B's notifications remain untouched
        self.assertEqual(Notification.objects.filter(user=self.customer_b, is_read=False).count(), 1)
