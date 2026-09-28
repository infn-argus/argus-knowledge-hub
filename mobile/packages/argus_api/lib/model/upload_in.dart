//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class UploadIn {
  /// Returns a new [UploadIn] instance.
  UploadIn({
    required this.contentType,
    required this.filename,
    required this.sha256,
    required this.size,
  });

  String contentType;

  String filename;

  String sha256;

  int size;

  @override
  bool operator ==(Object other) => identical(this, other) || other is UploadIn &&
    other.contentType == contentType &&
    other.filename == filename &&
    other.sha256 == sha256 &&
    other.size == size;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (contentType.hashCode) +
    (filename.hashCode) +
    (sha256.hashCode) +
    (size.hashCode);

  @override
  String toString() => 'UploadIn[contentType=$contentType, filename=$filename, sha256=$sha256, size=$size]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'content_type'] = this.contentType;
      json[r'filename'] = this.filename;
      json[r'sha256'] = this.sha256;
      json[r'size'] = this.size;
    return json;
  }

  /// Returns a new [UploadIn] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static UploadIn? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "UploadIn[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "UploadIn[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return UploadIn(
        contentType: mapValueOfType<String>(json, r'content_type')!,
        filename: mapValueOfType<String>(json, r'filename')!,
        sha256: mapValueOfType<String>(json, r'sha256')!,
        size: mapValueOfType<int>(json, r'size')!,
      );
    }
    return null;
  }

  static List<UploadIn> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <UploadIn>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = UploadIn.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, UploadIn> mapFromJson(dynamic json) {
    final map = <String, UploadIn>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = UploadIn.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of UploadIn-objects as value to a dart map
  static Map<String, List<UploadIn>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<UploadIn>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = UploadIn.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'content_type',
    'filename',
    'sha256',
    'size',
  };
}

