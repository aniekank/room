// Today's calendar events and open reminders, as JSON, via EventKit.
// usage: osascript -l JavaScript eventkit.js [days]   (macOS asks once for Calendars and Reminders)
ObjC.import('EventKit');
ObjC.import('Foundation');
function wait(fn) {  // EventKit's callbacks land on another thread; spin the run loop until they do
  var done = false, out = null;
  fn(function (v) { out = v; done = true; });
  var until = $.NSDate.dateWithTimeIntervalSinceNow(10);
  while (!done && $.NSDate.date.compare(until) < 0) $.NSRunLoop.currentRunLoop.runUntilDate($.NSDate.dateWithTimeIntervalSinceNow(0.05));
  return out;
}
function run(argv) {
  var days = parseInt(argv[0] || '1', 10), store = $.EKEventStore.alloc.init, out = {events: [], reminders: [], errors: []};
  var cal = $.NSCalendar.currentCalendar, start = cal.startOfDayForDate($.NSDate.date);
  var end = start.dateByAddingTimeInterval(86400 * days);
  var okE = wait(function (cb) { store.requestAccessToEntityTypeCompletion($.EKEntityTypeEvent, function (g) { cb(g); }); });
  if (okE) {
    var evs = store.eventsMatchingPredicate(store.predicateForEventsWithStartDateEndDateCalendars(start, end, $()));
    for (var i = 0; i < evs.count; i++) {
      var e = evs.objectAtIndex(i);
      out.events.push({title: ObjC.unwrap(e.title) || '', start: e.startDate.timeIntervalSince1970, end: e.endDate.timeIntervalSince1970,
                       allDay: !!e.allDay, where: ObjC.unwrap(e.location) || '', calendar: ObjC.unwrap(e.calendar.title) || ''});
    }
  } else out.errors.push('calendar: no access');
  var okR = wait(function (cb) { store.requestAccessToEntityTypeCompletion($.EKEntityTypeReminder, function (g) { cb(g); }); });
  if (okR) {
    var pred = store.predicateForIncompleteRemindersWithDueDateStartingEndingCalendars($(), end, $());
    var rs = wait(function (cb) { store.fetchRemindersMatchingPredicateCompletion(pred, function (r) { cb(r); }); });
    for (var j = 0; rs && j < rs.count; j++) {
      var r = rs.objectAtIndex(j), due = r.dueDateComponents;
      var d = due && !due.isNil() ? cal.dateFromComponents(due) : null;
      out.reminders.push({title: ObjC.unwrap(r.title) || '', due: d && !d.isNil() ? d.timeIntervalSince1970 : null, list: ObjC.unwrap(r.calendar.title) || ''});
    }
  } else out.errors.push('reminders: no access');
  return JSON.stringify(out);
}
