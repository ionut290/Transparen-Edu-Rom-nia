# Transparență Edu — activare comunitate Firebase

Aplicația poate rămâne în modul demo/local până la configurarea Firebase.

## Activare
1. Creează/alege proiectul Firebase pentru Transparență Edu.
2. Activează **Authentication** și furnizorul **Google**.
3. Creează baza **Cloud Firestore**.
4. În Firebase Console > Project settings > Your apps, creează aplicația Web.
5. Copiază `firebase-config.example.js` în `firebase-config.js` și completează configurația Web Firebase.
6. Adaugă domeniul GitHub Pages/Netlify folosit de aplicație la **Authentication > Settings > Authorized domains**.
7. Publică `firestore.rules` înainte de a activa comunitatea pentru utilizatori reali.
8. Pentru producție activează și **Firebase App Check**.

## Model de date
- `users/{uid}`: profil privat/minimal, rol și `schoolId`.
- `schools/{schoolId}/posts/{postId}`: discuții, idei și sondaje ale școlii.
- `nationalPosts/{postId}`: comunitatea națională.
- `privateRequests/{id}`: cereri private de ajutor/sesizări.
- `reports/{id}`: raportări pentru moderatori.

## Reguli de produs
- Nicio evaluare publică nominală a profesorilor.
- Cererile de ajutor și sesizările nu sunt feed public.
- Nu stoca în postări publice e-mail, telefon, adresă sau alte date personale sensibile.
- Rolurile privilegiate (`moderator`, `director`, `admin`) nu trebuie acordate de client; în producție trebuie administrate printr-un flux de încredere/server.
- Testează regulile cu Firebase Emulator înainte de lansare.

## Deploy reguli
```bash
firebase login
firebase use <PROJECT_ID>
firebase deploy --only firestore:rules
```

Configurarea Firebase Web nu este o cheie administrativă. Nu introduce niciodată service-account/private keys în repository sau în codul client.
