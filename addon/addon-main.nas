var main = func( addon ) {
  var root = addon.basePath;
  foreach(var f; ['fgatc.nas','fgatcdialog.nas'] ) {
    io.load_nasal( root ~ "/" ~ f, "fgatc" );
  }
}