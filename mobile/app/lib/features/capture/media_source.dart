import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:geolocator/geolocator.dart';
import 'package:image_picker/image_picker.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';

import '../../core/problem.dart';
import '../../domain/capture.dart';

/// Video, a recorded note and where the person is — what the field attaches besides photos (photo_source.dart).
/// Each comes back as a file to send like a photo. Tests replace it.
abstract class MediaSource {
  Future<PickedPhoto?> video();

  /// Where the person is, as a GeoJSON point with its accuracy and time.
  Future<PickedPhoto?> place();

  NoteRecorder recorder();
}

/// A recorded note: started, then stopped (kept) or cancelled.
abstract class NoteRecorder {
  Future<void> start();
  Future<PickedPhoto?> stop();
  Future<void> cancel();
}

class DeviceMediaSource implements MediaSource {
  final _picker = ImagePicker();

  @override
  Future<PickedPhoto?> video() async {
    final file = await _picker.pickVideo(
      source: kIsWeb ? ImageSource.gallery : ImageSource.camera,
      maxDuration: const Duration(minutes: 3), // a fault shown, not a film: the upload limit is 200 MB
    );
    if (file == null) return null;
    final name = file.name.isEmpty ? 'video.mp4' : file.name;
    return PickedPhoto(
        bytes: await file.readAsBytes(),
        name: name,
        mimeType: file.mimeType ?? (name.toLowerCase().endsWith('.mov') ? 'video/quicktime' : 'video/mp4'));
  }

  @override
  Future<PickedPhoto?> place() async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      throw Problem(ProblemCode.invalid, 'Location is turned off on this device.');
    }
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) permission = await Geolocator.requestPermission();
    if (permission == LocationPermission.denied || permission == LocationPermission.deniedForever) {
      throw Problem(ProblemCode.invalid, 'ARGUS Field may not use the location. Allow it in the system settings.');
    }
    final p = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(accuracy: LocationAccuracy.best, timeLimit: Duration(seconds: 30)));
    return placeFile(p.latitude, p.longitude, accuracy: p.accuracy, altitude: p.altitude, at: p.timestamp);
  }

  @override
  NoteRecorder recorder() => _DeviceRecorder();
}

/// A place as the file that is attached: a GeoJSON point (longitude first, as GeoJSON has it).
PickedPhoto placeFile(double lat, double lon, {double? accuracy, double? altitude, DateTime? at}) {
  final when = (at ?? DateTime.now()).toUtc();
  final json = {
    'type': 'Feature',
    'geometry': {'type': 'Point', 'coordinates': [lon, lat, if (altitude != null && altitude != 0) altitude]},
    'properties': {'accuracy_m': ?accuracy, 'recorded_at': when.toIso8601String()},
  };
  final stamp = when.toIso8601String().substring(0, 19).replaceAll(':', '-');
  return PickedPhoto(
      bytes: Uint8List.fromList(utf8.encode(jsonEncode(json))),
      name: 'location-$stamp.geojson',
      mimeType: 'application/geo+json');
}

/// Reads back what [placeFile] wrote: latitude, longitude and accuracy in metres.
({double lat, double lon, double? accuracy})? readPlace(List<int> bytes) {
  try {
    final m = jsonDecode(utf8.decode(bytes)) as Map;
    final c = (m['geometry'] as Map)['coordinates'] as List;
    return (
      lat: (c[1] as num).toDouble(),
      lon: (c[0] as num).toDouble(),
      accuracy: ((m['properties'] as Map?)?['accuracy_m'] as num?)?.toDouble(),
    );
  } catch (_) {
    return null;
  }
}

class _DeviceRecorder implements NoteRecorder {
  final _rec = AudioRecorder();
  String? _path;

  @override
  Future<void> start() async {
    if (!await _rec.hasPermission()) {
      throw Problem(ProblemCode.invalid, 'ARGUS Field may not use the microphone. Allow it in the system settings.');
    }
    final dir = await getTemporaryDirectory();
    _path = '${dir.path}/note-${DateTime.now().millisecondsSinceEpoch}.m4a';
    await _rec.start(const RecordConfig(encoder: AudioEncoder.aacLc, bitRate: 64000), path: _path!);
  }

  @override
  Future<PickedPhoto?> stop() async {
    final path = await _rec.stop();
    await _rec.dispose();
    if (path == null) return null;
    final f = File(path);
    final bytes = await f.readAsBytes();
    await f.delete();
    final stamp = DateTime.now().toIso8601String().substring(0, 19).replaceAll(':', '-');
    return PickedPhoto(bytes: bytes, name: 'note-$stamp.m4a', mimeType: 'audio/mp4');
  }

  @override
  Future<void> cancel() async {
    await _rec.cancel();
    await _rec.dispose();
  }
}
