//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class ChatAttachmentOut {
  /// Returns a new [ChatAttachmentOut] instance.
  ChatAttachmentOut({
    this.chars = 0,
    this.format,
    required this.name,
  });

  int chars;

  String? format;

  String name;

  @override
  bool operator ==(Object other) => identical(this, other) || other is ChatAttachmentOut &&
    other.chars == chars &&
    other.format == format &&
    other.name == name;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (chars.hashCode) +
    (format == null ? 0 : format!.hashCode) +
    (name.hashCode);

  @override
  String toString() => 'ChatAttachmentOut[chars=$chars, format=$format, name=$name]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'chars'] = this.chars;
    if (this.format != null) {
      json[r'format'] = this.format;
    } else {
      json[r'format'] = null;
    }
      json[r'name'] = this.name;
    return json;
  }

  /// Returns a new [ChatAttachmentOut] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static ChatAttachmentOut? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "ChatAttachmentOut[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "ChatAttachmentOut[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return ChatAttachmentOut(
        chars: mapValueOfType<int>(json, r'chars') ?? 0,
        format: mapValueOfType<String>(json, r'format'),
        name: mapValueOfType<String>(json, r'name')!,
      );
    }
    return null;
  }

  static List<ChatAttachmentOut> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <ChatAttachmentOut>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = ChatAttachmentOut.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, ChatAttachmentOut> mapFromJson(dynamic json) {
    final map = <String, ChatAttachmentOut>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = ChatAttachmentOut.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of ChatAttachmentOut-objects as value to a dart map
  static Map<String, List<ChatAttachmentOut>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<ChatAttachmentOut>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = ChatAttachmentOut.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'name',
  };
}

