import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'screens/map_screen.dart';
import 'state/map_state.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp, DeviceOrientation.landscapeLeft, DeviceOrientation.landscapeRight]);
  runApp(ChangeNotifierProvider(create: (_) => MapState(), child: const MapsApp()));
}

class MapsApp extends StatelessWidget {
  const MapsApp({super.key});
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'מפה אינטראקטיבית',
      debugShowCheckedModeBanner: false,
      locale: const Locale('he', 'IL'),
      theme: _theme(Brightness.light),
      darkTheme: _theme(Brightness.dark),
      themeMode: ThemeMode.dark,
      home: const MapScreen(),
    );
  }

  ThemeData _theme(Brightness b) {
    final cs = ColorScheme.fromSeed(seedColor: const Color(0xFF1565C0), brightness: b);
    return ThemeData(
      useMaterial3: true, colorScheme: cs,
      appBarTheme: AppBarTheme(
        backgroundColor: cs.surfaceContainerHigh, foregroundColor: cs.onSurface, elevation: 0, centerTitle: true,
        titleTextStyle: TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: cs.onSurface),
      ),
    );
  }
}
