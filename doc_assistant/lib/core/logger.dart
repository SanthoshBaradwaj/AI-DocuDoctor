import 'dart:developer' as dev;

void logI(String msg) => dev.log(msg, level: 800, name: 'INFO');
void logW(String msg) => dev.log(msg, level: 900, name: 'WARN');
void logE(String msg, [Object? err, StackTrace? st]) =>
    dev.log(msg, level: 1000, name: 'ERR', error: err, stackTrace: st);
