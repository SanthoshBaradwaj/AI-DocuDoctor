import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../services/auth_state.dart';

// Pages
import '../features/auth/login_page.dart';
import '../features/auth/signup_page.dart';
import '../features/auth/forgot_page.dart';
import '../features/home/home_page.dart';
import '../features/docs/docs_page.dart';
import '../features/docs/doc_detail_page.dart';
import '../features/analysis/analysis_page.dart';
import '../features/chat/chat_page.dart';
import '../features/upload/upload_page.dart';

final GlobalKey<NavigatorState> _rootNavigatorKey = GlobalKey<NavigatorState>();

final appRouter = GoRouter(
  navigatorKey: _rootNavigatorKey,
  initialLocation: '/login',
  refreshListenable: authState,
  routes: [
    GoRoute(
      path: '/login',
      builder: (context, state) => const LoginPage(),
    ),
    GoRoute(
      path: '/signup',
      builder: (context, state) => const SignupPage(),
    ),
    GoRoute(
      path: '/forgot',
      builder: (context, state) => const ForgotPage(),
    ),
    GoRoute(
      path: '/home',
      builder: (context, state) => const HomePage(),
      routes: [
        GoRoute(
          path: 'docs',
          builder: (context, state) => const DocsPage(),
        ),
        GoRoute(
          path: 'docs/detail/:id',
          builder: (context, state) {
            final idStr = state.pathParameters['id']!;
            return DocDetailPage(docId: int.parse(idStr));
          },
        ),
        GoRoute(
          path: 'docs/analysis',
          builder: (context, state) => const AnalysisPage(),
        ),
        GoRoute(
          path: 'chat',
          builder: (context, state) {
            // Check for docId query parameter
            final docIdStr = state.uri.queryParameters['docId'];
            final docId = docIdStr != null ? int.tryParse(docIdStr) : null;
            return ChatPage(docId: docId);
          },
        ),
        GoRoute(
          path: 'upload',
          builder: (context, state) => const UploadPage(),
        ),
      ],
    ),
  ],
  redirect: (context, state) {
    final loggedIn = authState.isLoggedIn;
    final loc = state.matchedLocation;
    final goingToAuth =
        (loc == '/login' || loc == '/signup' || loc == '/forgot');

    if (!loggedIn && !goingToAuth) return '/login';
    if (loggedIn && goingToAuth) return '/home';
    return null;
  },
);
