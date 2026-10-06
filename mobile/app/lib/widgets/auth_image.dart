import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../app/providers.dart';

/// An attachment or icon's bytes, cached for the session: every record that shows the same avatar or
/// thumbnail more than once (a list, then its detail page) asks for it only the first time.
final _imageBytesProvider = FutureProvider.autoDispose.family<Uint8List, String>((ref, attachmentUid) async {
  ref.keepAlive();
  return ref.watch(apiServiceProvider).getBytes('/v1/attachments/$attachmentUid');
});

/// A file behind the API's bearer auth, which a plain [Image.network] cannot fetch (flutter-app-design
/// §2.2: nothing talks HTTP but [ApiService]). Used for an asset's avatar and for attachment thumbnails.
class AuthImage extends ConsumerWidget {
  const AuthImage(this.attachmentUid, {super.key, this.width, this.height, this.fit = BoxFit.cover, this.placeholder});

  final String attachmentUid;
  final double? width;
  final double? height;
  final BoxFit fit;
  final Widget? placeholder;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final bytes = ref.watch(_imageBytesProvider(attachmentUid));
    return bytes.when(
      data: (b) => Image.memory(b, width: width, height: height, fit: fit,
          errorBuilder: (ctx, err, st) => _fallback(context)),
      loading: () => placeholder ?? SizedBox(width: width, height: height,
          child: const Center(child: SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)))),
      error: (err, st) => _fallback(context),
    );
  }

  Widget _fallback(BuildContext context) => SizedBox(
        width: width,
        height: height,
        child: Icon(Icons.broken_image_outlined, color: Theme.of(context).colorScheme.outline),
      );
}
