import 'dart:convert';

import 'package:argus_field/core/local_store.dart';
import 'package:argus_field/data/caching_client.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  late MemoryLocalStore store;
  late bool offline;
  late int status;
  late String scope;
  CachingClient client({Duration retention = const Duration(days: 7)}) => CachingClient(
        MockClient((req) async {
          if (offline) throw http.ClientException('down', req.url);
          return http.Response('{"uid":"a1"}', status, headers: {'content-type': 'application/json'});
        }),
        store,
        retention: retention,
        scope: () => scope,
      );

  setUp(() {
    store = MemoryLocalStore();
    offline = false;
    status = 200;
    scope = 'ws1|alice';
  });

  test('a record read once is served offline, labelled as a saved copy', () async {
    final c = client();
    await c.get(Uri.parse('https://a/v1/assets/a1'));
    offline = true;
    final r = await c.get(Uri.parse('https://a/v1/assets/a1'));
    expect(jsonDecode(r.body)['uid'], 'a1');
    expect(r.headers[CachingClient.offlineHeader], isNotNull);
  });

  test('searches and lookups are never kept', () async {
    final c = client();
    await c.get(Uri.parse('https://a/v1/hub/search?q=pump'));
    await c.get(Uri.parse('https://a/v1/lookup/SN-1'));
    expect(await store.readPrefix(CachingClient.prefix), isEmpty);
    offline = true;
    await expectLater(c.get(Uri.parse('https://a/v1/hub/search?q=pump')), throwsA(isA<http.ClientException>()));
  });

  test('a record that is gone, or no longer visible, leaves the device', () async {
    final c = client();
    await c.get(Uri.parse('https://a/v1/assets/a1'));
    status = 404;
    await c.get(Uri.parse('https://a/v1/assets/a1'));
    offline = true;
    await expectLater(c.get(Uri.parse('https://a/v1/assets/a1')), throwsA(isA<http.ClientException>()));
  });

  test('a copy older than the retention is not served', () async {
    await client().get(Uri.parse('https://a/v1/assets/a1'));
    offline = true;
    final expired = client(retention: Duration.zero);
    await expectLater(expired.get(Uri.parse('https://a/v1/assets/a1')), throwsA(isA<http.ClientException>()));
    expect(await store.readPrefix(CachingClient.prefix), isEmpty);
  });

  test("another person's or workspace's copies are not served", () async {
    final c = client();
    await c.get(Uri.parse('https://a/v1/assets/a1'));
    scope = 'ws1|bob';
    offline = true;
    await expectLater(c.get(Uri.parse('https://a/v1/assets/a1')), throwsA(isA<http.ClientException>()));
  });

  group('fresh copies', () {
    late int calls;
    CachingClient freshClient() => CachingClient(
          MockClient((req) async {
            calls++;
            return http.Response('{"uid":"a1","n":$calls}', 200, headers: {'content-type': 'application/json'});
          }),
          store,
          retention: const Duration(days: 7),
          scope: () => scope,
          fresh: const Duration(minutes: 1),
        );

    setUp(() => calls = 0);

    test('what was just read is shown again without asking ARGUS', () async {
      final c = freshClient();
      await c.get(Uri.parse('https://a/v1/assets/a1'));
      final again = await c.get(Uri.parse('https://a/v1/assets/a1'));
      expect(calls, 1);
      expect(jsonDecode(again.body)['n'], 1);
      expect(again.headers[CachingClient.offlineHeader], isNull, reason: 'fresh, not an offline copy');
    });

    test('a change sent from here makes every earlier copy stale', () async {
      final c = freshClient();
      await c.get(Uri.parse('https://a/v1/assets/a1'));
      await c.put(Uri.parse('https://a/v1/assets/a1'), body: '{}');
      final after = await c.get(Uri.parse('https://a/v1/assets/a1'));
      expect(calls, 3);
      expect(jsonDecode(after.body)['n'], 3, reason: 'what the person just changed is never hidden');
    });

    test('what is never kept is never served fresh either', () async {
      final c = freshClient();
      await c.get(Uri.parse('https://a/v1/hub/search?q=x'));
      await c.get(Uri.parse('https://a/v1/hub/search?q=x'));
      expect(calls, 2);
    });
  });

  test('the oldest copies go first when there are too many', () async {
    final c = CachingClient(
      MockClient((req) async => http.Response('{}', 200, headers: {'content-type': 'application/json'})),
      store,
      retention: const Duration(days: 7),
      scope: () => scope,
      maxEntries: 2,
    );
    for (final id in ['a1', 'a2', 'a3']) {
      await c.get(Uri.parse('https://a/v1/assets/$id'));
      await Future<void>.delayed(const Duration(milliseconds: 5));
    }
    expect((await store.stamps(CachingClient.prefix)).length, 2);
  });
}
