# ML Kit text recognition (Read printed text on the scan screen): the plugin can ask for the Chinese,
# Devanagari, Japanese and Korean recognizers, which this app does not bundle — Latin script only, for
# nameplates and labels. Their classes are absent on purpose.
-dontwarn com.google.mlkit.vision.text.chinese.**
-dontwarn com.google.mlkit.vision.text.devanagari.**
-dontwarn com.google.mlkit.vision.text.japanese.**
-dontwarn com.google.mlkit.vision.text.korean.**
