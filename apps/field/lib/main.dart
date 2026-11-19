import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:material_ui/material_ui.dart';
import 'package:geolocator/geolocator.dart';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:sqflite/sqflite.dart';

const apiBase = String.fromEnvironment('API_BASE', defaultValue: 'http://10.0.2.2:8000/api/v1');

String newReportId() {
  final random = Random.secure();
  final bytes = List<int>.generate(16, (_) => random.nextInt(256));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  final hex = bytes.map((byte) => byte.toRadixString(16).padLeft(2, '0')).join();
  return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20)}';
}

Future<Database> openOutbox() async {
  final path = p.join(await getDatabasesPath(), 'liveslide_outbox.db');
  return openDatabase(path, version: 1, onCreate: (db, _) async {
    await db.execute('''CREATE TABLE reports(
      id TEXT PRIMARY KEY, photo_path TEXT NOT NULL, lat REAL NOT NULL, lon REAL NOT NULL,
      captured_at TEXT NOT NULL, note TEXT, created_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued')''');
  });
}

void main() => runApp(const LiveslideApp());

class LiveslideApp extends StatelessWidget {
  const LiveslideApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Liveslide Field', theme: ThemeData(colorSchemeSeed: const Color(0xff24765a), useMaterial3: true),
    home: const FieldHome());
}

class FieldHome extends StatefulWidget {
  const FieldHome({super.key});
  @override
  State<FieldHome> createState() => _FieldHomeState();
}

class _FieldHomeState extends State<FieldHome> {
  final noteController = TextEditingController();
  File? photo;
  List<Map<String, Object?>> items = [];
  String? token;
  String status = 'Ready';
  bool busy = false;
  late Database db;

  @override
  void initState() { super.initState(); _init(); }
  Future<void> _init() async {
    db = await openOutbox();
    final prefs = await SharedPreferences.getInstance();
    token = prefs.getString('token');
    await _reload();
    if (mounted) setState(() {});
  }
  Future<void> _reload() async {
    if (!mounted) return;
    items = await db.query('reports', orderBy: 'created_at DESC');
    setState(() {});
  }
  Future<void> _login() async {
    final email = TextEditingController(text: 'volunteer@example.test');
    final password = TextEditingController();
    final ok = await showDialog<bool>(context: context, builder: (context) => AlertDialog(
      title: const Text('Sign in'), content: Column(mainAxisSize: MainAxisSize.min, children: [
        TextField(controller: email, decoration: const InputDecoration(labelText: 'Email')),
        TextField(controller: password, obscureText: true, decoration: const InputDecoration(labelText: 'Password'))]),
      actions: [TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
        FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Sign in'))]));
    if (ok != true) return;
    try {
      final response = await http.post(Uri.parse('$apiBase/auth/login'), headers: {'Content-Type':'application/json'},
        body: jsonEncode({'email':email.text, 'password':password.text}));
      if (response.statusCode != 200) throw Exception('Sign-in failed (${response.statusCode})');
      token = jsonDecode(response.body)['access_token'] as String;
      final prefs = await SharedPreferences.getInstance(); await prefs.setString('token', token!);
      setState(() => status = 'Signed in');
    } catch (e) { setState(() => status = e.toString()); }
  }
  Future<void> _capture() async {
    final picked = await ImagePicker().pickImage(source: ImageSource.camera, imageQuality: 80, maxWidth: 1600);
    if (picked != null) setState(() => photo = File(picked.path));
  }
  Future<void> _saveReport() async {
    if (photo == null) { setState(() => status = 'Take a photo before saving.'); return; }
    setState(() => busy = true);
    try {
      final permission = await Geolocator.checkPermission();
      var allowed = permission;
      if (permission == LocationPermission.denied) allowed = await Geolocator.requestPermission();
      if (allowed == LocationPermission.denied || allowed == LocationPermission.deniedForever) {
        throw Exception('Location permission is required to attach a report location.');
      }
      final position = await Geolocator.getCurrentPosition();
      final dir = await getApplicationDocumentsDirectory();
      final id = newReportId();
      final savedPhoto = await photo!.copy(p.join(dir.path, 'report_$id.jpg'));
      await db.insert('reports', {'id':id, 'photo_path':savedPhoto.path, 'lat':position.latitude,
        'lon':position.longitude, 'captured_at':DateTime.now().toUtc().toIso8601String(),
        'note':noteController.text.trim(), 'created_at':DateTime.now().toUtc().toIso8601String(), 'status':'queued'});
      photo = null; noteController.clear();
      await _reload();
      setState(() => status = 'Saved securely on this device. It will sync when you choose Sync.');
    } catch (e) { setState(() => status = e.toString()); }
    finally { setState(() => busy = false); }
  }
  Future<void> _sync() async {
    if (token == null) { await _login(); if (token == null) return; }
    final connectivity = await Connectivity().checkConnectivity();
    if (connectivity.contains(ConnectivityResult.none)) { setState(() => status = 'Offline. Reports remain safely queued.'); return; }
    setState(() => busy = true);
    int sent = 0;
    for (final row in items.where((x) => x['status'] == 'queued')) {
      try {
        final request = http.MultipartRequest('POST', Uri.parse('$apiBase/reports'))
          ..headers['Authorization'] = 'Bearer $token'
          ..fields.addAll({'client_report_id':row['id'].toString(), 'lat':row['lat'].toString(),
            'lon':row['lon'].toString(), 'captured_at':row['captured_at'].toString(), 'device_id':'field-app',
            'note':(row['note'] ?? '').toString()})
          ..files.add(await http.MultipartFile.fromPath('photo', row['photo_path'].toString(), filename:'evidence.jpg'));
        final response = await request.send();
        if (response.statusCode < 300) { await db.delete('reports', where:'id = ?', whereArgs:[row['id']]); sent++; }
        else { setState(() => status = 'Sync paused: API returned ${response.statusCode}. Reports are queued.'); break; }
      } catch (_) { setState(() => status = 'Could not reach server. Reports are queued for retry.'); break; }
    }
    await _reload();
    if (sent > 0) setState(() => status = 'Synced $sent report${sent == 1 ? '' : 's'}.');
    setState(() => busy = false);
  }
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Liveslide Field'), actions:[TextButton(onPressed:_login, child:Text(token == null ? 'Sign in' : 'Account'))]),
    body: ListView(padding: const EdgeInsets.all(18), children:[
      Card(child:Padding(padding:const EdgeInsets.all(16), child:Column(crossAxisAlignment:CrossAxisAlignment.start, children:[
        const Text('Community landslide report', style:TextStyle(fontSize:20,fontWeight:FontWeight.bold)),
        const SizedBox(height:6), const Text('Reports are stored offline first and uploaded only after you sync.'),
        const SizedBox(height:14), OutlinedButton.icon(onPressed:busy ? null : _capture, icon:const Icon(Icons.camera_alt), label:Text(photo == null ? 'Take photo' : 'Photo ready')),
        if(photo != null) Padding(padding:const EdgeInsets.symmetric(vertical:8), child:Image.file(photo!, height:150, fit:BoxFit.cover)),
        TextField(controller:noteController, maxLength:500, decoration:const InputDecoration(labelText:'Short note (optional)', border:OutlineInputBorder())),
        const SizedBox(height:8), FilledButton.icon(onPressed:busy ? null : _saveReport, icon:const Icon(Icons.save_alt), label:const Text('Save offline report')),
      ]))),
      const SizedBox(height:10), Row(mainAxisAlignment:MainAxisAlignment.spaceBetween, children:[Text('Outbox · ${items.length}', style:const TextStyle(fontSize:18,fontWeight:FontWeight.bold)), FilledButton.icon(onPressed:busy ? null : _sync, icon:const Icon(Icons.sync), label:const Text('Sync'))]),
      Text(status, style:TextStyle(color:Theme.of(context).colorScheme.primary)),
      ...items.map((row)=>ListTile(leading:const Icon(Icons.pending_actions), title:Text(row['note']?.toString().isNotEmpty == true ? row['note'].toString() : 'Photo report'), subtitle:Text('${row['status']} · ${row['created_at']}'), trailing:Image.file(File(row['photo_path'].toString()),width:42,height:42,fit:BoxFit.cover))),
    ]));
}
