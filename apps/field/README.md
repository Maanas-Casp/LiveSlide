# Liveslide Field

The Flutter app captures a photo and device location, writes the report plus its image path to a local SQLite outbox, then uploads queued reports when the volunteer explicitly taps **Sync**. A client-generated report ID makes retries idempotent.

From this folder, generate the Android/iOS runner files once with:

```sh
flutter create --project-name liveslide_field --platforms android,ios .
```

Then use `flutter pub get` and `flutter run`. Android uses the emulator host mapping `10.0.2.2` by default. For a phone, pass a reachable API URL with `--dart-define=API_BASE=http://<host>:8000/api/v1`. The Android manifest permits cleartext HTTP for local development; deploy behind HTTPS and disable that setting before real field use. Add the matching iOS camera and location usage descriptions to the generated `ios/Runner/Info.plist` before running on iOS.

Demo volunteer login is `volunteer@example.test` / `liveslide-dev` after the API seed step. Reports and photos remain on device until an explicit successful sync.
