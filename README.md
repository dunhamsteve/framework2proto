# framework2proto

This is a quick and dirty script I wrote to derive a protobuf description from a Mach-O executable.

It leverages objdump to dissassemble the `writeTo:` methods generated by protoc and tries to extract the schema
with some simplistic pattern matching. It also uses the ObjC metadata to resolve the types of fields and scans
"ReadFrom" functions to determine the types of arrays of objects.

## Example usage

To dump a protobuf schema from the serializers in the CloudKit framework:

    python3 framework2proto.py /System/Library/Frameworks/CloudKit.framework/CloudKit

