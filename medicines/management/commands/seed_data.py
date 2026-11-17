from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from inventory.models import Inventory
from medicines.models import Medicine
from pharmacies.models import Pharmacy
from requests_app.models import AvailabilityRequest, Notification

User = get_user_model()

class Command(BaseCommand):
    help = "Populate demonstration dataset for MediFind final-year project presentation."

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Starting MediFind sample data population..."))

        with transaction.atomic():
            # 1. Admin Account
            admin_user, created = User.objects.get_or_create(
                username='admin',
                defaults={
                    'email': 'admin@medifind.test',
                    'role': 'ADMIN',
                    'phone_number': '+91 9900011100',
                    'is_staff': True,
                    'is_superuser': True,
                }
            )
            admin_user.set_password('admin123')
            admin_user.save()
            self.stdout.write(self.style.SUCCESS("[OK] Admin user created: admin / admin123"))

            # 2. Customer Accounts
            customers_data = [
                ('customer1', 'customer1@medifind.test', '+91 9888811111', 'John', 'Doe'),
                ('customer2', 'customer2@medifind.test', '+91 9888822222', 'Sarah', 'Smith'),
                ('customer3', 'customer3@medifind.test', '+91 9888833333', 'Rahul', 'Sharma'),
            ]
            customers = []
            for username, email, phone, first, last in customers_data:
                c_user, _ = User.objects.get_or_create(
                    username=username,
                    defaults={
                        'email': email,
                        'role': 'CUSTOMER',
                        'phone_number': phone,
                        'first_name': first,
                        'last_name': last,
                    }
                )
                c_user.set_password('password123')
                c_user.save()
                customers.append(c_user)
            self.stdout.write(self.style.SUCCESS(f"[OK] {len(customers)} Customer accounts created (password: password123)"))

            # 3. Pharmacy Owners & Pharmacies (5 Approved Pharmacies + 1 Pending)
            pharmacies_specs = [
                {
                    'owner_username': 'apollo_owner',
                    'email': 'apollo@medifind.test',
                    'phone': '+91 9111100001',
                    'name': 'Apollo Healthcare Store',
                    'reg_no': 'DEMO-HYD-AP-101',
                    'address': 'Road No. 12, Banjara Hills',
                    'city': 'Hyderabad',
                    'state': 'Telangana',
                    'pincode': '500034',
                    'lat': 17.415582,
                    'lng': 78.435783,
                    'approved': True,
                },
                {
                    'owner_username': 'medplus_owner',
                    'email': 'medplus@medifind.test',
                    'phone': '+91 9111100002',
                    'name': 'MedPlus Pharma Hub',
                    'reg_no': 'DEMO-HYD-MP-102',
                    'address': 'Cyber Towers Junction, Madhapur',
                    'city': 'Hyderabad',
                    'state': 'Telangana',
                    'pincode': '500081',
                    'lat': 17.448293,
                    'lng': 78.391485,
                    'approved': True,
                },
                {
                    'owner_username': 'wellness_owner',
                    'email': 'wellness@medifind.test',
                    'phone': '+91 9111100003',
                    'name': 'Wellness Forever 24x7',
                    'reg_no': 'DEMO-BLR-WF-103',
                    'address': '100 Feet Road, HAL 2nd Stage, Indiranagar',
                    'city': 'Bengaluru',
                    'state': 'Karnataka',
                    'pincode': '560038',
                    'lat': 12.978369,
                    'lng': 77.640836,
                    'approved': True,
                },
                {
                    'owner_username': 'netmeds_owner',
                    'email': 'netmeds@medifind.test',
                    'phone': '+91 9111100004',
                    'name': 'NetMeds Point Care',
                    'reg_no': 'DEMO-BLR-NM-104',
                    'address': '80 Feet Main Road, 4th Block, Koramangala',
                    'city': 'Bengaluru',
                    'state': 'Karnataka',
                    'pincode': '560034',
                    'lat': 12.935193,
                    'lng': 77.624481,
                    'approved': True,
                },
                {
                    'owner_username': 'care_owner',
                    'email': 'care@medifind.test',
                    'phone': '+91 9111100005',
                    'name': 'Care & Cure Community Chemist',
                    'reg_no': 'DEMO-DEL-CC-105',
                    'address': 'Connaught Place, Inner Circle',
                    'city': 'New Delhi',
                    'state': 'Delhi',
                    'pincode': '110001',
                    'lat': 28.631451,
                    'lng': 77.216667,
                    'approved': True,
                },
                {
                    'owner_username': 'pending_owner',
                    'email': 'pending@medifind.test',
                    'phone': '+91 9111100006',
                    'name': 'Metro Life Pharmacy',
                    'reg_no': 'DEMO-HYD-ML-106',
                    'address': 'Station Road, Secunderabad',
                    'city': 'Hyderabad',
                    'state': 'Telangana',
                    'pincode': '500003',
                    'lat': 17.439930,
                    'lng': 78.498274,
                    'approved': False,  # For testing admin approval flow
                },
            ]

            pharmacies = []
            for spec in pharmacies_specs:
                p_user, _ = User.objects.get_or_create(
                    username=spec['owner_username'],
                    defaults={
                        'email': spec['email'],
                        'role': 'PHARMACY',
                        'phone_number': spec['phone'],
                    }
                )
                p_user.set_password('password123')
                p_user.save()

                pharmacy, _ = Pharmacy.objects.get_or_create(
                    registration_number=spec['reg_no'],
                    defaults={
                        'owner': p_user,
                        'pharmacy_name': spec['name'],
                        'address': spec['address'],
                        'city': spec['city'],
                        'state': spec['state'],
                        'pincode': spec['pincode'],
                        'phone_number': spec['phone'],
                        'latitude': spec['lat'],
                        'longitude': spec['lng'],
                        'is_approved': spec['approved'],
                    }
                )
                pharmacies.append(pharmacy)

            self.stdout.write(self.style.SUCCESS(f"[OK] {len(pharmacies)} Demo Pharmacies initialized."))

            # 4. 30 Medicines Master Catalogue
            medicines_catalog = [
                # Antibiotics
                ('Amoxicillin 500mg', 'Amoxicillin Trihydrate', '500mg', 'Capsule', 'Antibiotics', 'Broad-spectrum penicillin antibiotic used for bacterial infections.'),
                ('Azithromycin 500mg', 'Azithromycin Dihydrate', '500mg', 'Tablet', 'Antibiotics', 'Macrolide antibiotic for respiratory tract and skin infections.'),
                ('Ciprofloxacin 500mg', 'Ciprofloxacin Hydrochloride', '500mg', 'Tablet', 'Antibiotics', 'Fluoroquinolone antibiotic for urinary tract and systemic infections.'),
                ('Cefixime 200mg', 'Cefixime Trihydrate', '200mg', 'Tablet', 'Antibiotics', 'Third-generation cephalosporin antibiotic.'),
                ('Doxycycline 100mg', 'Doxycycline Hyclate', '100mg', 'Capsule', 'Antibiotics', 'Tetracycline antibiotic used for acne and respiratory infections.'),
                ('Augmentin 625 Duo', 'Amoxicillin + Clavulanic Acid', '625mg', 'Tablet', 'Antibiotics', 'Penicillin antibiotic with beta-lactamase inhibitor.'),

                # Analgesics & Antipyretic
                ('Dolo 650', 'Paracetamol', '650mg', 'Tablet', 'Antipyretic', 'Fever reducer and mild-to-moderate analgesic.'),
                ('Crocin Advance 500', 'Paracetamol', '500mg', 'Tablet', 'Antipyretic', 'Fast-acting fever and headache relief tablet.'),
                ('Combiflam', 'Ibuprofen + Paracetamol', '400mg/325mg', 'Tablet', 'Analgesics & Pain Relief', 'Dual action anti-inflammatory and painkiller.'),
                ('Brufen 400', 'Ibuprofen', '400mg', 'Tablet', 'Analgesics & Pain Relief', 'Non-steroidal anti-inflammatory drug (NSAID).'),
                ('Volini Gel', 'Diclofenac Diethylamine', '30g', 'Ointment', 'Analgesics & Pain Relief', 'Topical analgesic for musculoskeletal pain and sprains.'),
                ('Zerodol-SP', 'Aceclofenac + Paracetamol + Serratiopeptidase', '100mg/325mg/15mg', 'Tablet', 'Analgesics & Pain Relief', 'Pain and swelling relief formulation.'),

                # Antidiabetic
                ('Glycomet 500', 'Metformin Hydrochloride', '500mg', 'Tablet', 'Antidiabetic', 'First-line medication for Type 2 diabetes management.'),
                ('Januvia 100mg', 'Sitagliptin Phosphate', '100mg', 'Tablet', 'Antidiabetic', 'DPP-4 inhibitor for glycemic control.'),
                ('Amaryl 2mg', 'Glimepiride', '2mg', 'Tablet', 'Antidiabetic', 'Sulfonylurea oral antidiabetic drug.'),
                ('Lantus Solostar', 'Insulin Glargine', '100 IU/ml (3ml)', 'Injection', 'Antidiabetic', 'Long-acting basal human insulin analog pen.'),

                # Cardiovascular & Blood Pressure
                ('Telma 40', 'Telmisartan', '40mg', 'Tablet', 'Cardiovascular', 'Angiotensin II receptor antagonist for hypertension.'),
                ('Amlopres 5', 'Amlodipine Besylate', '5mg', 'Tablet', 'Cardiovascular', 'Calcium channel blocker for high blood pressure and angina.'),
                ('Atorva 10', 'Atorvastatin Calcium', '10mg', 'Tablet', 'Cardiovascular', 'Statin medication to lower LDL cholesterol.'),
                ('Ecosprin 75', 'Aspirin', '75mg', 'Tablet', 'Cardiovascular', 'Blood thinner to prevent blood clots and cardiac episodes.'),

                # Respiratory & Anti-Allergic
                ('Allegra 120mg', 'Fexofenadine Hydrochloride', '120mg', 'Tablet', 'Respiratory & Anti-Allergic', 'Non-drowsy antihistamine for allergic rhinitis and hives.'),
                ('Cetzine 10mg', 'Cetirizine Hydrochloride', '10mg', 'Tablet', 'Respiratory & Anti-Allergic', 'Antihistamine for seasonal allergies and sneezing.'),
                ('Montair-LC', 'Levocetirizine + Montelukast', '5mg/10mg', 'Tablet', 'Respiratory & Anti-Allergic', 'Combination treatment for allergic asthma and rhinitis.'),
                ('Asthalin Inhaler', 'Salbutamol', '100mcg (200 md)', 'Inhaler', 'Respiratory & Anti-Allergic', 'Bronchodilator for rapid relief of asthma bronchospasm.'),
                ('Budecort 200', 'Budesonide', '200mcg', 'Inhaler', 'Respiratory & Anti-Allergic', 'Corticosteroid inhaler for asthma maintenance.'),

                # Gastrointestinal
                ('Pan 40', 'Pantoprazole Sodium', '40mg', 'Tablet', 'Gastrointestinal', 'Proton pump inhibitor for GERD and acidity.'),
                ('Omez 20', 'Omeprazole', '20mg', 'Capsule', 'Gastrointestinal', 'Acid reducer for heartburn and stomach ulcers.'),
                ('Digene Gel Mint', 'Magnesium Hydroxide + Aluminium Hydroxide', '200ml', 'Syrup', 'Gastrointestinal', 'Antacid suspension for instant acidity relief.'),

                # Vitamins & Supplements
                ('Limcee 500', 'Ascorbic Acid (Vitamin C)', '500mg', 'Tablet', 'Vitamins & Supplements', 'Chewable Vitamin C supplement for immunity.'),
                ('Zincovit', 'Multivitamins + Minerals + Zinc', 'Tablet', 'Tablet', 'Vitamins & Supplements', 'Nutritional supplement for general wellness.'),
                ('Shelcal 500', 'Calcium + Vitamin D3', '500mg/250 IU', 'Tablet', 'Vitamins & Supplements', 'Bone health supplement.'),
            ]

            saved_medicines = []
            for name, gen, strength, form, cat, desc in medicines_catalog:
                med, _ = Medicine.objects.get_or_create(
                    medicine_name=name,
                    defaults={
                        'generic_name': gen,
                        'strength': strength,
                        'dosage_form': form,
                        'category': cat,
                        'description': desc,
                    }
                )
                saved_medicines.append(med)

            self.stdout.write(self.style.SUCCESS(f"[OK] {len(saved_medicines)} Medicines populated in Master Catalogue."))

            # 5. Inventory Records (At least 60 realistic records across the 5 approved pharmacies)
            approved_pharmacies = [p for p in pharmacies if p.is_approved]
            
            # Distribution quantities: a mix of in_stock (>10), low_stock (1-10), and out_of_stock (0)
            stock_patterns = [
                # Apollo: Strong stock
                (approved_pharmacies[0], [
                    (saved_medicines[0], 45), (saved_medicines[1], 25), (saved_medicines[6], 120),
                    (saved_medicines[7], 80), (saved_medicines[8], 30), (saved_medicines[12], 50),
                    (saved_medicines[13], 15), (saved_medicines[15], 8), (saved_medicines[16], 35),
                    (saved_medicines[20], 40), (saved_medicines[23], 12), (saved_medicines[25], 60),
                    (saved_medicines[28], 100), (saved_medicines[29], 75),
                ]),
                # MedPlus: Varied stock with some low stock
                (approved_pharmacies[1], [
                    (saved_medicines[0], 18), (saved_medicines[2], 30), (saved_medicines[6], 65),
                    (saved_medicines[9], 4), (saved_medicines[10], 22), (saved_medicines[12], 40),
                    (saved_medicines[14], 14), (saved_medicines[15], 0), (saved_medicines[17], 28),
                    (saved_medicines[21], 55), (saved_medicines[22], 6), (saved_medicines[26], 30),
                    (saved_medicines[27], 15), (saved_medicines[30], 45),
                ]),
                # Wellness Forever: 24/7 store with emergency and respiratory stock
                (approved_pharmacies[2], [
                    (saved_medicines[1], 35), (saved_medicines[3], 20), (saved_medicines[6], 90),
                    (saved_medicines[8], 45), (saved_medicines[11], 16), (saved_medicines[13], 25),
                    (saved_medicines[16], 30), (saved_medicines[18], 50), (saved_medicines[19], 70),
                    (saved_medicines[23], 0), (saved_medicines[24], 18), (saved_medicines[25], 40),
                    (saved_medicines[28], 80), (saved_medicines[29], 60),
                ]),
                # NetMeds Point Care: High diabetes and cardiac inventory
                (approved_pharmacies[3], [
                    (saved_medicines[4], 22), (saved_medicines[5], 18), (saved_medicines[6], 40),
                    (saved_medicines[7], 5), (saved_medicines[12], 85), (saved_medicines[13], 32),
                    (saved_medicines[14], 24), (saved_medicines[15], 10), (saved_medicines[17], 40),
                    (saved_medicines[18], 30), (saved_medicines[22], 25), (saved_medicines[25], 50),
                    (saved_medicines[30], 35),
                ]),
                # Care & Cure: Broad community chemistery
                (approved_pharmacies[4], [
                    (saved_medicines[0], 20), (saved_medicines[1], 15), (saved_medicines[2], 25),
                    (saved_medicines[6], 110), (saved_medicines[8], 20), (saved_medicines[10], 12),
                    (saved_medicines[12], 30), (saved_medicines[16], 22), (saved_medicines[20], 35),
                    (saved_medicines[21], 40), (saved_medicines[23], 5), (saved_medicines[25], 45),
                    (saved_medicines[27], 20), (saved_medicines[28], 60),
                ]),
            ]

            total_inventory_items = 0
            for pharmacy, items in stock_patterns:
                for med, qty in items:
                    inv, _ = Inventory.objects.get_or_create(
                        pharmacy=pharmacy,
                        medicine=med,
                        defaults={'quantity': qty}
                    )
                    inv.quantity = qty
                    inv.save()
                    total_inventory_items += 1

            self.stdout.write(self.style.SUCCESS(f"[OK] {total_inventory_items} Sample Inventory records generated."))

            # 6. Sample Availability Requests & Inquiries
            sample_requests = [
                {
                    'customer': customers[0],
                    'pharmacy': approved_pharmacies[0],
                    'medicine': saved_medicines[6],  # Dolo 650
                    'qty': 2,
                    'msg': "Urgent: High fever since evening, can you hold 2 strips?",
                    'status': 'CONFIRMED',
                    'resp': "2 strips reserved at billing counter 2. Please collect by 8:30 PM.",
                },
                {
                    'customer': customers[1],
                    'pharmacy': approved_pharmacies[1],
                    'medicine': saved_medicines[15],  # Insulin Glargine
                    'qty': 1,
                    'msg': "Prescription order. Do you have cold-storage Insulin Glargine pen in stock?",
                    'status': 'UNAVAILABLE',
                    'resp': "Stock currently exhausted. Fresh refrigerated delivery scheduled for tomorrow 10:00 AM.",
                },
                {
                    'customer': customers[2],
                    'pharmacy': approved_pharmacies[2],
                    'medicine': saved_medicines[23],  # Asthalin Inhaler
                    'qty': 1,
                    'msg': "Need Asthalin Inhaler urgently for patient with sudden asthma wheezing.",
                    'status': 'PENDING',
                    'resp': "",
                },
                {
                    'customer': customers[0],
                    'pharmacy': approved_pharmacies[3],
                    'medicine': saved_medicines[12],  # Glycomet 500
                    'qty': 3,
                    'msg': "Monthly refill of Glycomet 500mg (3 strips).",
                    'status': 'CONFIRMED',
                    'resp': "Confirmed available! Ready for pickup anytime before 10 PM.",
                },
            ]

            for s_req in sample_requests:
                req, _ = AvailabilityRequest.objects.get_or_create(
                    customer=s_req['customer'],
                    pharmacy=s_req['pharmacy'],
                    medicine=s_req['medicine'],
                    defaults={
                        'quantity_requested': s_req['qty'],
                        'request_message': s_req['msg'],
                        'status': s_req['status'],
                        'pharmacy_response': s_req['resp'],
                    }
                )

            self.stdout.write(self.style.SUCCESS(f"[OK] {len(sample_requests)} Sample Availability Requests created."))

            # 7. Sample Notifications
            Notification.objects.create(
                user=customers[0],
                message="Apollo Healthcare Store confirmed your request for Dolo 650."
            )
            Notification.objects.create(
                user=customers[1],
                message="MedPlus Pharma Hub updated your inquiry status for Insulin Glargine."
            )
            Notification.objects.create(
                user=approved_pharmacies[2].owner,
                message="New urgent availability request received for Asthalin Inhaler from customer3."
            )

            self.stdout.write(self.style.SUCCESS("[OK] Demonstration dataset populated successfully!"))
