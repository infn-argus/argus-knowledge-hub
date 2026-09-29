import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../../app/providers.dart';
import '../../core/link_parser.dart';

/// Scan a QR code, a DataMatrix or a barcode on a label (flutter-app-design §5.2). What was read
/// is parsed before anything happens: only ARGUS links are followed, other links are refused and
/// plain values are looked up. Typing the label is always possible (a damaged label, no camera).
class ScanScreen extends ConsumerStatefulWidget {
  const ScanScreen({super.key, this.pick = false});

  /// Return what was read to the screen that asked, instead of opening it.
  final bool pick;

  @override
  ConsumerState<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends ConsumerState<ScanScreen> {
  final _controller = MobileScannerController(
    formats: const [BarcodeFormat.qrCode, BarcodeFormat.dataMatrix, BarcodeFormat.code128, BarcodeFormat.code39],
  );
  final _typed = TextEditingController();
  bool _handling = false;
  String? _refusal;

  @override
  void dispose() {
    _controller.dispose();
    _typed.dispose();
    super.dispose();
  }

  void _handle(String raw) {
    if (_handling) return;
    final result = parseScan(raw, linkHost: ref.read(configProvider).linkHost);
    switch (result) {
      case ArgusPath(:final path):
        _handling = true;
        widget.pick ? context.pop(path) : context.pushReplacement(path);
      case LabelValue(:final value):
        _handling = true;
        widget.pick ? context.pop('/lookup/${Uri.encodeComponent(value)}')
            : context.pushReplacement('/lookup/${Uri.encodeComponent(value)}');
      case Refused(:final reason):
        setState(() => _refusal = reason);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Scan label'),
        actions: [
          IconButton(
            tooltip: 'Torch',
            icon: const Icon(Icons.flashlight_on_outlined),
            onPressed: () => _controller.toggleTorch(),
          ),
        ],
      ),
      body: Column(children: [
        Expanded(
          child: Stack(fit: StackFit.expand, children: [
            MobileScanner(
              controller: _controller,
              onDetect: (capture) {
                final value = capture.barcodes.map((b) => b.rawValue).whereType<String>().firstOrNull;
                if (value != null) _handle(value);
              },
              errorBuilder: (context, error) => Container(
                color: Colors.black,
                alignment: Alignment.center,
                padding: const EdgeInsets.all(24),
                child: Text(
                  error.errorCode == MobileScannerErrorCode.permissionDenied
                      ? 'The camera is not allowed. Allow it in the system settings, or type the label below.'
                      : 'The camera is not available here. Type the label below.',
                  style: const TextStyle(color: Colors.white),
                  textAlign: TextAlign.center,
                ),
              ),
            ),
            Center(
              child: Container(
                width: 240,
                height: 240,
                decoration: BoxDecoration(
                  border: Border.all(color: Colors.white70, width: 2),
                  borderRadius: BorderRadius.circular(16),
                ),
              ),
            ),
          ]),
        ),
        if (_refusal != null)
          Container(
            key: const Key('scan-refusal'),
            width: double.infinity,
            color: Theme.of(context).colorScheme.errorContainer,
            padding: const EdgeInsets.all(12),
            child: Text(_refusal!, style: TextStyle(color: Theme.of(context).colorScheme.onErrorContainer)),
          ),
        SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: TextField(
              key: const Key('scan-typed'),
              controller: _typed,
              textInputAction: TextInputAction.go,
              decoration: InputDecoration(
                labelText: 'Or type the label',
                border: const OutlineInputBorder(),
                suffixIcon: IconButton(icon: const Icon(Icons.arrow_forward), onPressed: () => _handle(_typed.text)),
              ),
              onSubmitted: _handle,
            ),
          ),
        ),
      ]),
    );
  }
}
