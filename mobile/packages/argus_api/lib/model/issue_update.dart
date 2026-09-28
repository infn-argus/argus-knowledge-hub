//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class IssueUpdate {
  /// Returns a new [IssueUpdate] instance.
  IssueUpdate({
    this.assetUid,
    this.assignee,
    this.attributes,
    this.description,
    this.dueDate,
    this.labels = const [],
    this.priority,
    this.schemaUid,
    this.state,
    this.title,
  });

  String? assetUid;

  String? assignee;

  Object? attributes;

  String? description;

  DateTime? dueDate;

  List<String>? labels;

  String? priority;

  String? schemaUid;

  String? state;

  String? title;

  @override
  bool operator ==(Object other) => identical(this, other) || other is IssueUpdate &&
    other.assetUid == assetUid &&
    other.assignee == assignee &&
    other.attributes == attributes &&
    other.description == description &&
    other.dueDate == dueDate &&
    _deepEquality.equals(other.labels, labels) &&
    other.priority == priority &&
    other.schemaUid == schemaUid &&
    other.state == state &&
    other.title == title;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (assetUid == null ? 0 : assetUid!.hashCode) +
    (assignee == null ? 0 : assignee!.hashCode) +
    (attributes == null ? 0 : attributes!.hashCode) +
    (description == null ? 0 : description!.hashCode) +
    (dueDate == null ? 0 : dueDate!.hashCode) +
    (labels == null ? 0 : labels!.hashCode) +
    (priority == null ? 0 : priority!.hashCode) +
    (schemaUid == null ? 0 : schemaUid!.hashCode) +
    (state == null ? 0 : state!.hashCode) +
    (title == null ? 0 : title!.hashCode);

  @override
  String toString() => 'IssueUpdate[assetUid=$assetUid, assignee=$assignee, attributes=$attributes, description=$description, dueDate=$dueDate, labels=$labels, priority=$priority, schemaUid=$schemaUid, state=$state, title=$title]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.assetUid != null) {
      json[r'asset_uid'] = this.assetUid;
    } else {
      json[r'asset_uid'] = null;
    }
    if (this.assignee != null) {
      json[r'assignee'] = this.assignee;
    } else {
      json[r'assignee'] = null;
    }
    if (this.attributes != null) {
      json[r'attributes'] = this.attributes;
    } else {
      json[r'attributes'] = null;
    }
    if (this.description != null) {
      json[r'description'] = this.description;
    } else {
      json[r'description'] = null;
    }
    if (this.dueDate != null) {
      json[r'due_date'] = this.dueDate!.toUtc().toIso8601String();
    } else {
      json[r'due_date'] = null;
    }
    if (this.labels != null) {
      json[r'labels'] = this.labels;
    } else {
      json[r'labels'] = null;
    }
    if (this.priority != null) {
      json[r'priority'] = this.priority;
    } else {
      json[r'priority'] = null;
    }
    if (this.schemaUid != null) {
      json[r'schema_uid'] = this.schemaUid;
    } else {
      json[r'schema_uid'] = null;
    }
    if (this.state != null) {
      json[r'state'] = this.state;
    } else {
      json[r'state'] = null;
    }
    if (this.title != null) {
      json[r'title'] = this.title;
    } else {
      json[r'title'] = null;
    }
    return json;
  }

  /// Returns a new [IssueUpdate] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static IssueUpdate? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "IssueUpdate[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "IssueUpdate[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return IssueUpdate(
        assetUid: mapValueOfType<String>(json, r'asset_uid'),
        assignee: mapValueOfType<String>(json, r'assignee'),
        attributes: mapValueOfType<Object>(json, r'attributes'),
        description: mapValueOfType<String>(json, r'description'),
        dueDate: mapDateTime(json, r'due_date', r''),
        labels: json[r'labels'] is Iterable
            ? (json[r'labels'] as Iterable).cast<String>().toList(growable: false)
            : const [],
        priority: mapValueOfType<String>(json, r'priority'),
        schemaUid: mapValueOfType<String>(json, r'schema_uid'),
        state: mapValueOfType<String>(json, r'state'),
        title: mapValueOfType<String>(json, r'title'),
      );
    }
    return null;
  }

  static List<IssueUpdate> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <IssueUpdate>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = IssueUpdate.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, IssueUpdate> mapFromJson(dynamic json) {
    final map = <String, IssueUpdate>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = IssueUpdate.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of IssueUpdate-objects as value to a dart map
  static Map<String, List<IssueUpdate>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<IssueUpdate>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = IssueUpdate.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
  };
}

