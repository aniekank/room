// iCloud Drive state for one file, as JSON: is it uploaded, is it on this Mac.
// usage: osascript -l JavaScript icloud.js <path>
ObjC.import('Foundation');
function run(argv) {
  var u = $.NSURL.fileURLWithPath(argv[0]);
  var keys = $([$.NSURLUbiquitousItemIsUploadedKey, $.NSURLUbiquitousItemIsUploadingKey, $.NSURLUbiquitousItemDownloadingStatusKey]);
  var v = u.resourceValuesForKeysError(keys, null);
  if (!v || v.isNil()) return JSON.stringify({error: 'unreadable'});
  function b(k) { var x = v.objectForKey(k); return !x.isNil() && x.boolValue; }
  var dl = v.objectForKey($.NSURLUbiquitousItemDownloadingStatusKey);
  return JSON.stringify({uploaded: b($.NSURLUbiquitousItemIsUploadedKey), uploading: b($.NSURLUbiquitousItemIsUploadingKey),
                         local: dl.isNil() || dl.js === $.NSURLUbiquitousItemDownloadingStatusCurrent.js});
}
