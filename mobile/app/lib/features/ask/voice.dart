import 'dart:async';

import 'package:flutter_tts/flutter_tts.dart';
import 'package:speech_to_text/speech_recognition_result.dart';
import 'package:speech_to_text/speech_to_text.dart';

/// Speaking to the assistant and hearing its answer, with the phone's own speech recognition and
/// voice: nothing is recorded or sent but the words recognised, which go as the typed question
/// would. Tests replace it.
abstract class Voice {
  /// Whether the device can listen (a recogniser, and the microphone allowed). Asks once.
  Future<bool> canListen();

  /// Listen until the person pauses: [onWords] gets the words as they are recognised, with
  /// `last` true once. Returns when listening has started.
  Future<void> listen(void Function(String words, bool last) onWords);

  Future<void> stopListening();

  /// Read [text] aloud; completes when it has been said, or [quiet] was called.
  Future<void> speak(String text);

  Future<void> quiet();
}

class DeviceVoice implements Voice {
  final _speech = SpeechToText();
  final _tts = FlutterTts();
  bool? _ready;
  void Function(String, bool)? _onWords;
  String _heard = '';

  @override
  Future<bool> canListen() async {
    _ready ??= await _speech.initialize(
      onError: (_) => _finish(),
      // "done" also comes when nothing was heard: the listener is still told it is over.
      onStatus: (s) {
        if (s == SpeechToText.doneStatus || s == SpeechToText.notListeningStatus) _finish();
      },
    );
    return _ready!;
  }

  void _finish() {
    final f = _onWords;
    _onWords = null;
    f?.call(_heard, true);
  }

  @override
  Future<void> listen(void Function(String words, bool last) onWords) async {
    if (!await canListen()) return;
    await quiet();
    _heard = '';
    _onWords = onWords;
    await _speech.listen(
      onResult: (SpeechRecognitionResult r) {
        _heard = r.recognizedWords;
        if (r.finalResult) {
          _finish();
        } else {
          _onWords?.call(_heard, false);
        }
      },
      listenOptions: SpeechListenOptions(
        partialResults: true,
        listenMode: ListenMode.dictation,
        pauseFor: const Duration(seconds: 3),
        listenFor: const Duration(seconds: 60),
      ),
    );
  }

  @override
  Future<void> stopListening() => _speech.stop();

  @override
  Future<void> speak(String text) async {
    await _tts.awaitSpeakCompletion(true);
    await _tts.speak(text);
  }

  @override
  Future<void> quiet() async {
    await _tts.stop();
  }
}

/// The answer as it should be heard: no Markdown marks, no link targets, no code fences.
String spoken(String text) => text
    .replaceAll(RegExp(r'```[\s\S]*?```'), ' ')
    .replaceAllMapped(RegExp(r'\[([^\]]+)\]\([^)]*\)'), (m) => m[1]!)
    .replaceAll(RegExp(r'[*_`#>|]'), '')
    .replaceAll(RegExp(r'^\s*[-•]\s+', multiLine: true), '')
    .replaceAll(RegExp(r'[ \t]+'), ' ')
    .trim();
