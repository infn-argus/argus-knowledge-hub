import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// A69: no provider credential and no model prompt in the application (revision §24.6, I-MOB-7).
/// The app talks only to ARGUS; the AI Intake runs on the server. This scans the sources that go
/// into the build, the generated client included; `tool/check_build.sh` scans a built bundle too.
final forbidden = <String, RegExp>{
  'a provider key': RegExp(r'''\b(sk-[A-Za-z0-9_-]{20,}|sk-ant-[A-Za-z0-9_-]{10,}|AIza[0-9A-Za-z_-]{30,})'''),
  'a literal bearer token': RegExp(r'''Bearer [A-Za-z0-9._-]{16,}'''),
  'an API key assigned in code': RegExp(r'''(api[_-]?key|secret|password)\s*[:=]\s*['"][^'"$]{6,}['"]''',
      caseSensitive: false),
  'a model provider endpoint': RegExp(r'''(api\.openai\.com|api\.anthropic\.com|generativelanguage\.googleapis|/chat/completions)'''),
  'a model prompt': RegExp(r'''(You are (a|an) [a-z]+ (assistant|model)|system prompt|<\|im_start\|>)''', caseSensitive: false),
};

Iterable<File> _sources(String dir) => Directory(dir)
    .listSync(recursive: true)
    .whereType<File>()
    .where((f) => f.path.endsWith('.dart') || f.path.endsWith('.yaml') || f.path.endsWith('.json'));

void main() {
  test('the app and its generated client carry no credential, prompt or provider endpoint', () {
    final findings = <String>[];
    for (final dir in ['lib', '../packages/argus_api/lib', 'web', 'android/app/src', 'ios/Runner']) {
      if (!Directory(dir).existsSync()) continue;
      for (final f in _sources(dir)) {
        final text = f.readAsStringSync();
        forbidden.forEach((what, re) {
          for (final m in re.allMatches(text)) {
            findings.add('${f.path}: $what: ${m.group(0)}');
          }
        });
      }
    }
    expect(findings, isEmpty);
  });

  test('the scanner would catch them', () {
    expect(forbidden['a provider key']!.hasMatch('const k = "sk-proj-ABCDEFGHIJKLMNOPQRSTUV";'), isTrue);
    expect(forbidden['a model prompt']!.hasMatch("'You are a helpful assistant'"), isTrue);
    expect(forbidden['a model provider endpoint']!.hasMatch('https://api.openai.com/v1/chat/completions'), isTrue);
    expect(forbidden['an API key assigned in code']!.hasMatch("apiKey: 'abcdef123'"), isTrue);
  });
}
