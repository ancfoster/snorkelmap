// media validate - checks a photo in the browser before it is uploaded

(function (global) {
  'use strict';

  var rules = null;

  function getRules() {
    if (rules) return rules;
    var el = document.getElementById('media-rules');
    rules = el ? JSON.parse(el.textContent) : null;
    if (!rules) throw new Error('media-rules json_script block is missing');
    return rules;
  }

  // helpers - small shared utilities

  function fill(template, values) {
    return template.replace(/\{(\w+)\}/g, function (match, key) {
      return Object.prototype.hasOwnProperty.call(values, key)
        ? String(values[key]) : match;
    });
  }

  function formatBytes(bytes) {
    if (bytes >= 1024 * 1024) {
      var mb = bytes / (1024 * 1024);
      return (mb >= 10 ? Math.round(mb) : mb.toFixed(1)) + 'MB';
    }
    return Math.max(1, Math.round(bytes / 1024)) + 'KB';
  }

  function hexAt(bytes, offset, byteLength) {
    var out = '';
    for (var i = offset; i < offset + byteLength; i++) {
      if (i >= bytes.length) return '';
      out += bytes[i].toString(16).padStart(2, '0');
    }
    return out.toUpperCase();
  }

  function readHead(file, byteLength) {
    return file.slice(0, byteLength).arrayBuffer()
      .then(function (buffer) { return new Uint8Array(buffer); });
  }

  function reject(reasonKey, message) {
    return { ok: false, reason: reasonKey, message: message };
  }

  // format sniffing - identify a file from its opening bytes

  function conditionMatches(head, condition) {
    for (var i = 0; i < condition.any_of.length; i++) {
      var candidate = condition.any_of[i];
      if (hexAt(head, condition.offset, candidate.length / 2) === candidate) {
        return true;
      }
    }
    return false;
  }

  function signatureMatches(head, signatures) {
    return signatures.some(function (signature) {
      return signature.every(function (condition) {
        return conditionMatches(head, condition);
      });
    });
  }

  function looksLikeSvg(head, svg) {
    var slice = head.subarray(0, svg.sniff_bytes);
    var text;
    try {
      text = new TextDecoder('utf-8', { fatal: false }).decode(slice).toLowerCase();
    } catch (e) {
      return false;
    }
    return svg.markers.some(function (marker) { return text.indexOf(marker) !== -1; });
  }

  // format - returns the matched entry, or null when unrecognised
  function sniff(head) {
    var r = getRules();
    var i;
    for (i = 0; i < r.accepted.length; i++) {
      if (signatureMatches(head, r.accepted[i].signatures)) {
        return { format: r.accepted[i], accepted: true };
      }
    }
    for (i = 0; i < r.rejected.length; i++) {
      if (signatureMatches(head, r.rejected[i].signatures)) {
        return { format: r.rejected[i], accepted: false };
      }
    }
    if (looksLikeSvg(head, r.svg)) {
      return {
        format: { mime: r.svg.mime, label: 'SVG', message: r.svg.message },
        accepted: false,
      };
    }
    return null;
  }

  // heif reader - walks the box structure of a heic file

  var HEIF_SCAN_BYTES = 2 * 1024 * 1024;

  function eachBox(view, start, end, visit) {
    var offset = start;
    while (offset + 8 <= end) {
      var size = view.getUint32(offset);
      var type = String.fromCharCode(
        view.getUint8(offset + 4), view.getUint8(offset + 5),
        view.getUint8(offset + 6), view.getUint8(offset + 7)
      );
      var headerSize = 8;
      if (size === 1) {
        if (offset + 16 > end) return;
        // 64 bit size - only the low word is usable at our scan sizes
        size = view.getUint32(offset + 12);
        headerSize = 16;
      } else if (size === 0) {
        size = end - offset;
      }
      if (size < headerSize || offset + size > end) return;
      visit(type, offset + headerSize, offset + size);
      offset += size;
    }
  }

  function findBox(view, start, end, wanted) {
    var found = null;
    eachBox(view, start, end, function (type, payloadStart, payloadEnd) {
      if (!found && type === wanted) {
        found = { start: payloadStart, end: payloadEnd };
      }
    });
    return found;
  }

  function readPrimaryItemId(view, meta) {
    var pitm = findBox(view, meta.start, meta.end, 'pitm');
    if (!pitm) return null;
    var version = view.getUint8(pitm.start);
    var at = pitm.start + 4;                       // skip version and flags
    return version === 0 ? view.getUint16(at) : view.getUint32(at);
  }

  function readPropertyIndexes(view, meta, itemId) {
    var iprp = findBox(view, meta.start, meta.end, 'iprp');
    if (!iprp) return null;
    var ipma = findBox(view, iprp.start, iprp.end, 'ipma');
    if (!ipma) return null;

    var version = view.getUint8(ipma.start);
    var flags = (view.getUint8(ipma.start + 1) << 16)
              | (view.getUint8(ipma.start + 2) << 8)
              | view.getUint8(ipma.start + 3);
    var wideIndexes = (flags & 1) === 1;

    var at = ipma.start + 4;
    var entryCount = view.getUint32(at);
    at += 4;

    for (var entry = 0; entry < entryCount && at < ipma.end; entry++) {
      var entryId;
      if (version < 1) { entryId = view.getUint16(at); at += 2; }
      else             { entryId = view.getUint32(at); at += 4; }

      var associationCount = view.getUint8(at);
      at += 1;

      var indexes = [];
      for (var a = 0; a < associationCount; a++) {
        if (wideIndexes) {
          indexes.push(view.getUint16(at) & 0x7fff);
          at += 2;
        } else {
          indexes.push(view.getUint8(at) & 0x7f);
          at += 1;
        }
      }
      if (entryId === itemId) return indexes;
    }
    return null;
  }

  function readIspe(view, box) {
    return {
      width: view.getUint32(box.start + 4),        // skip version and flags
      height: view.getUint32(box.start + 8),
    };
  }

  // ispe - largest one in the file, when the primary item is unresolved
  function largestIspe(view, meta) {
    var iprp = findBox(view, meta.start, meta.end, 'iprp');
    if (!iprp) return null;
    var ipco = findBox(view, iprp.start, iprp.end, 'ipco');
    if (!ipco) return null;

    var best = null;
    eachBox(view, ipco.start, ipco.end, function (type, payloadStart, payloadEnd) {
      if (type !== 'ispe') return;
      var size = readIspe(view, { start: payloadStart, end: payloadEnd });
      if (!best || size.width * size.height > best.width * best.height) {
        best = size;
      }
    });
    return best;
  }

  // item location - find an item's bytes using the iloc offsets
  function heifItemRange(view, end, wantedType) {
    var meta = findBox(view, 0, end, 'meta');
    if (!meta) return null;
    var children = { start: meta.start + 4, end: meta.end };

    var iinf = findBox(view, children.start, children.end, 'iinf');
    var iloc = findBox(view, children.start, children.end, 'iloc');
    if (!iinf || !iloc) return null;

    // iinf - entry count is 16 or 32 bits depending on version
    var iinfVersion = view.getUint8(iinf.start);
    var entriesStart = iinf.start + 4 + (iinfVersion === 0 ? 2 : 4);

    var wantedId = null;
    eachBox(view, entriesStart, iinf.end, function (type, start) {
      if (wantedId !== null || type !== 'infe') return;
      var version = view.getUint8(start);
      if (version < 2) return;                  // pre-heif layout, not used here
      var at = start + 4;
      var itemId = version === 2 ? view.getUint16(at) : view.getUint32(at);
      at += version === 2 ? 2 : 4;
      at += 2;                                  // protection index
      var itemType = String.fromCharCode(
        view.getUint8(at), view.getUint8(at + 1),
        view.getUint8(at + 2), view.getUint8(at + 3)
      );
      if (itemType === wantedType) wantedId = itemId;
    });
    if (wantedId === null) return null;

    var version = view.getUint8(iloc.start);
    var at = iloc.start + 4;
    var offsetSize = view.getUint8(at) >> 4;
    var lengthSize = view.getUint8(at) & 0x0f;
    var baseOffsetSize = view.getUint8(at + 1) >> 4;
    var indexSize = version >= 1 ? (view.getUint8(at + 1) & 0x0f) : 0;
    at += 2;

    var count;
    if (version < 2) { count = view.getUint16(at); at += 2; }
    else             { count = view.getUint32(at); at += 4; }

    function readSized(size) {
      if (size === 4) { var v = view.getUint32(at); at += 4; return v; }
      if (size === 8) {
        // low word - anything larger than that is past what we accept
        var v8 = view.getUint32(at + 4); at += 8; return v8;
      }
      if (size === 2) { var v2 = view.getUint16(at); at += 2; return v2; }
      if (size === 1) { var v1 = view.getUint8(at); at += 1; return v1; }
      return 0;
    }

    for (var i = 0; i < count && at < iloc.end; i++) {
      var itemId;
      if (version < 2) { itemId = view.getUint16(at); at += 2; }
      else             { itemId = view.getUint32(at); at += 4; }
      if (version === 1 || version === 2) at += 2;   // construction method
      at += 2;                                       // data reference index
      var baseOffset = readSized(baseOffsetSize);
      var extentCount = view.getUint16(at); at += 2;

      for (var e = 0; e < extentCount; e++) {
        if (indexSize) readSized(indexSize);
        var extentOffset = readSized(offsetSize);
        var extentLength = readSized(lengthSize);
        // first extent - a split exif item is legal but cameras do not make one
        if (itemId === wantedId && e === 0) {
          return { start: baseOffset + extentOffset, length: extentLength };
        }
      }
    }
    return null;
  }

  function heifDimensions(buffer) {
    var view = new DataView(buffer);
    var meta = findBox(view, 0, buffer.byteLength, 'meta');
    if (!meta) return null;

    // meta - a fullbox, so children start after version and flags
    var metaChildren = { start: meta.start + 4, end: meta.end };

    var itemId = readPrimaryItemId(view, metaChildren);
    if (itemId !== null) {
      var indexes = readPropertyIndexes(view, metaChildren, itemId);
      var iprp = findBox(view, metaChildren.start, metaChildren.end, 'iprp');
      var ipco = iprp && findBox(view, iprp.start, iprp.end, 'ipco');
      if (indexes && ipco) {
        var properties = [];
        eachBox(view, ipco.start, ipco.end, function (type, payloadStart, payloadEnd) {
          properties.push({ type: type, start: payloadStart, end: payloadEnd });
        });
        for (var i = 0; i < indexes.length; i++) {
          var property = properties[indexes[i] - 1];   // ipco is 1 indexed
          if (property && property.type === 'ispe') {
            return readIspe(view, property);
          }
        }
      }
    }
    return largestIspe(view, metaChildren);
  }

  // dimensions - read the width and height

  function decodeDimensions(file) {
    if (typeof global.createImageBitmap !== 'function') {
      return imageElementDimensions(file);
    }
    return global.createImageBitmap(file).then(function (bitmap) {
      var size = { width: bitmap.width, height: bitmap.height, decoded: true };
      if (bitmap.close) bitmap.close();
      return size;
    }).catch(function () { return imageElementDimensions(file); });
  }

  // fallback - for browsers without createImageBitmap for blobs
  function imageElementDimensions(file) {
    if (typeof Image !== 'function' || typeof URL === 'undefined'
        || typeof URL.createObjectURL !== 'function') {
      return Promise.resolve(null);
    }
    return new Promise(function (resolve) {
      var url = URL.createObjectURL(file);
      var img = new Image();
      img.onload = function () {
        resolve({ width: img.naturalWidth, height: img.naturalHeight, decoded: true });
        URL.revokeObjectURL(url);
      };
      img.onerror = function () {
        resolve(null);
        URL.revokeObjectURL(url);
      };
      img.src = url;
    });
  }

  function containerDimensions(scan) {
    if (!scan) return null;
    var size = heifDimensions(scan);
    return size ? { width: size.width, height: size.height, decoded: false } : null;
  }

  // exif - read from the file by offset, it can sit after the image data
  function heifExifBuffer(file, scan) {
    if (!scan) return Promise.resolve(null);
    var range;
    try {
      range = heifItemRange(new DataView(scan), scan.byteLength, 'Exif');
    } catch (e) { return Promise.resolve(null); }
    if (!range || !range.length) return Promise.resolve(null);

    return file.slice(range.start, range.start + range.length).arrayBuffer()
      .then(function (payload) {
        if (payload.byteLength < 8) return null;
        // offset - the item opens with a 4 byte offset to the tiff header
        var headerOffset = new DataView(payload).getUint32(0);
        var tiffStart = 4 + headerOffset;
        if (tiffStart >= payload.byteLength) return null;
        return wrapTiffAsJpeg(new Uint8Array(payload, tiffStart));
      })
      .catch(function () { return null; });
  }

  // wrap - exifr needs a jpeg shell around a bare tiff block
  var APP1_MAX_PAYLOAD = 65533 - 8;

  function wrapTiffAsJpeg(tiff) {
    if (tiff.byteLength > APP1_MAX_PAYLOAD) return null;
    var segmentLength = 2 + 6 + tiff.byteLength;   // length field, exif prefix, data
    var out = new Uint8Array(12 + tiff.byteLength + 2);
    out.set([
      0xff, 0xd8,                                  // soi
      0xff, 0xe1,                                  // app1
      (segmentLength >> 8) & 0xff, segmentLength & 0xff,
      0x45, 0x78, 0x69, 0x66, 0x00, 0x00,          // exif prefix
    ], 0);
    out.set(tiff, 12);
    out.set([0xff, 0xd9], 12 + tiff.byteLength);   // eoi
    return out;
  }

  // capture metadata - date, time and coordinates

  function pad(n) { return String(n).padStart(2, '0'); }

  function wallClock(date) {
    // date check - not instanceof, exifr may build it in another realm
    if (Object.prototype.toString.call(date) !== '[object Date]') return null;
    if (isNaN(date.getTime())) return null;
    return date.getFullYear() + '-' + pad(date.getMonth() + 1) + '-' +
           pad(date.getDate()) + 'T' + pad(date.getHours()) + ':' +
           pad(date.getMinutes()) + ':' + pad(date.getSeconds());
  }

  function readCaptureMetadata(file, scan) {
    if (typeof global.exifr === 'undefined') return Promise.resolve({});

    // source - the tiff block for heic, the whole file for everything else
    var source = scan
      ? heifExifBuffer(file, scan).then(function (tiff) { return tiff || file; })
      : Promise.resolve(file);

    return source.then(function (input) {
      return global.exifr.parse(input, { tiff: true, exif: true, gps: true });
    }).then(function (exif) {
      exif = exif || {};
      var out = {};
      var capturedAt = wallClock(exif.DateTimeOriginal || exif.CreateDate || null);
      if (capturedAt) out.capturedAt = capturedAt;
      if (exif.OffsetTimeOriginal) out.capturedAtOffset = exif.OffsetTimeOriginal;
      if (typeof exif.latitude === 'number' && typeof exif.longitude === 'number'
          && isFinite(exif.latitude) && isFinite(exif.longitude)) {
        out.latitude = exif.latitude;
        out.longitude = exif.longitude;
      }
      return out;
    }).catch(function () { return {}; });
  }

  // the gate - the single entry point that accepts or rejects a file

  function validateFile(file) {
    var r = getRules();
    var limits = r.limits;
    var messages = r.messages;
    var name = file.name || 'This file';

    // order - decide the format before the size
    return readHead(file, Math.max(r.svg.sniff_bytes, 64)).then(function (head) {
      var match = sniff(head);
      if (!match) {
        return reject('unsupported', fill(messages.unsupported, { name: name }));
      }
      if (!match.accepted) {
        return reject('rejected_format', fill(match.format.message, { name: name }));
      }

      if (file.size < limits.min_bytes) {
        return reject('empty', fill(messages.empty, { name: name }));
      }
      if (file.size > limits.max_bytes) {
        return reject('too_heavy', fill(messages.too_heavy, {
          name: name,
          size: formatBytes(file.size),
          limit: formatBytes(limits.max_bytes),
        }));
      }

      var format = match.format;

      // buffer - opened once and reused for dimensions and exif
      var scanned = format.mime === 'image/heic'
        ? file.slice(0, HEIF_SCAN_BYTES).arrayBuffer().catch(function () { return null; })
        : Promise.resolve(null);

      var scan = null;
      return scanned.then(function (buffer) {
        scan = buffer;
        return decodeDimensions(file);
      }).then(function (size) {
        return size || containerDimensions(scan);
      }).then(function (size) {
        if (!size) {
          return reject('unreadable', fill(messages.unreadable, { name: name }));
        }

        var shortest = Math.min(size.width, size.height);
        var longest = Math.max(size.width, size.height);
        var megapixels = (size.width * size.height) / 1000000;

        if (shortest < limits.min_dimension) {
          return reject('too_small', fill(messages.too_small, {
            name: name, width: size.width, height: size.height,
            min: limits.min_dimension,
          }));
        }
        if (longest > limits.max_dimension) {
          return reject('too_wide', fill(messages.too_wide, {
            name: name, width: size.width, height: size.height,
            max: limits.max_dimension,
          }));
        }
        if (megapixels > limits.max_megapixels) {
          return reject('too_many_pixels', fill(messages.too_many_pixels, {
            name: name, megapixels: megapixels.toFixed(1),
            max: limits.max_megapixels,
          }));
        }

        return readCaptureMetadata(file, scan).then(function (metadata) {
          return {
            ok: true,
            file: file,
            name: name,
            mime: format.mime,
            extension: format.extension,
            label: format.label,
            bytes: file.size,
            width: size.width,
            height: size.height,
            // no preview - true only for heic on chromium and firefox
            previewable: size.decoded === true,
            capturedAt: metadata.capturedAt || null,
            capturedAtOffset: metadata.capturedAtOffset || null,
            latitude: typeof metadata.latitude === 'number' ? metadata.latitude : null,
            longitude: typeof metadata.longitude === 'number' ? metadata.longitude : null,
          };
        });
      });
    }).catch(function (error) {
      console.warn('Could not validate ' + name, error);
      return reject('unreadable', fill(messages.unreadable, { name: name }));
    });
  }

  global.SMMedia = {
    rules: getRules,
    validateFile: validateFile,
    formatBytes: formatBytes,
    fill: fill,
    // exported for the test suite
    _sniff: sniff,
    _heifDimensions: heifDimensions,
    _heifItemRange: heifItemRange,
  };
}(window));
