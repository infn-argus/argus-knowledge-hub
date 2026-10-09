import 'dart:io';

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:google_mlkit_text_recognition/google_mlkit_text_recognition.dart';
import 'package:path_provider/path_provider.dart';

import '../../domain/capture.dart';

/// Reads the printed text on a nameplate or a label — a serial, an inventory number, a key — from a photo,
/// on the device (ML Kit): nothing is sent anywhere to be read. Tests replace it.
abstract class TextReader {
  bool get available;
  Future<String> read(PickedPhoto photo);
}

class DeviceTextReader implements TextReader {
  @override
  bool get available => !kIsWeb && (Platform.isAndroid || Platform.isIOS);

  @override
  Future<String> read(PickedPhoto photo) async {
    final dir = await getTemporaryDirectory();
    final file = File('${dir.path}/argus-ocr-${DateTime.now().microsecondsSinceEpoch}.jpg');
    await file.writeAsBytes(photo.bytes, flush: true);
    final recognizer = TextRecognizer(script: TextRecognitionScript.latin);
    try {
      return (await recognizer.processImage(InputImage.fromFilePath(file.path))).text;
    } finally {
      await recognizer.close();
      if (await file.exists()) await file.delete();
    }
  }
}

/// What in a photo's text could be a label's value, most likely first: a value after "S/N", "Serial",
/// "Inv." and the like, then codes that mix letters and digits (how serials and keys look), then long
/// numbers. Words and short numbers (a voltage, a year) are left out.
List<String> labelCandidates(String text) {
  final out = <String>[];
  void add(String v) {
    final t = v.trim().replaceAll(RegExp(r'^[^A-Za-z0-9]+|[^A-Za-z0-9]+$'), '');
    if (t.length >= 4 && t.length <= 64 && !out.contains(t)) out.add(t);
  }

  final prefixed = RegExp(
      r'(?:S\s*/\s*N|SN|SER(?:IAL)?(?:\s*(?:NO|NR|N°|NUMBER|#))?|MATR(?:ICOLA)?|INV(?:ENTAR(?:Y|IO))?(?:\s*(?:NO|NR|N°|#))?|ASSET(?:\s*TAG)?|P\s*/\s*N|ID)\s*[.:#]?\s*([A-Za-z0-9][A-Za-z0-9\-_/.:]{2,})',
      caseSensitive: false);
  for (final m in prefixed.allMatches(text)) {
    add(m.group(1)!);
  }
  final tokens = text.split(RegExp(r'[\s,;]+')).where((t) => t.isNotEmpty).toList();
  bool hasDigit(String t) => RegExp(r'\d').hasMatch(t);
  bool hasLetter(String t) => RegExp(r'[A-Za-z]').hasMatch(t);
  for (final t in tokens) {
    if (hasDigit(t) && hasLetter(t)) add(t);
  }
  for (final t in tokens) {
    if (RegExp(r'^\d{6,}$').hasMatch(t)) add(t);
  }
  // A whole line, for a key with spaces in it ("SPARC ELM QUA01" printed across).
  for (final line in text.split('\n').map((l) => l.trim())) {
    if (RegExp(r'^[A-Za-z0-9-]+( [A-Za-z0-9-]+)+$').hasMatch(line) && hasDigit(line) && hasLetter(line) &&
        line.length <= 40 && !prefixed.hasMatch(line)) {
      add(line);
    }
  }
  return out;
}
