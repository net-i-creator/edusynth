<?php
/**
 * Proxies /api/* requests to the Render backend.
 * Locally handles POST /api/support → partners@умбаза.рф via PHP mail().
 */
$BACKEND = 'https://edusynth.onrender.com';
$SUPPORT_TO = 'partners@xn--80aabzw5b.xn--p1ai'; // partners@умбаза.рф

$uri = $_SERVER['REQUEST_URI'];
$path = parse_url($uri, PHP_URL_PATH);
$query = parse_url($uri, PHP_URL_QUERY);
$method = $_SERVER['REQUEST_METHOD'];
$body = file_get_contents('php://input');

// --- Local support form handler ---
if ($method === 'POST' && preg_match('#/api/support/?$#', $path)) {
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');

    $data = json_decode($body ?: '{}', true);
    if (!is_array($data)) {
        http_response_code(400);
        echo json_encode(['detail' => 'Некорректный запрос'], JSON_UNESCAPED_UNICODE);
        exit;
    }

    $email = trim((string)($data['email'] ?? ''));
    $message = trim((string)($data['message'] ?? ''));

    if ($email === '' || $message === '' || !filter_var($email, FILTER_VALIDATE_EMAIL)) {
        http_response_code(400);
        echo json_encode(['detail' => 'Заполните корректный email и сообщение'], JSON_UNESCAPED_UNICODE);
        exit;
    }

    $subject = '=?UTF-8?B?' . base64_encode('Обратная связь УмБаза от ' . $email) . '?=';
    $bodyText = "От: {$email}\n\n{$message}\n";
    $headers = [
        'MIME-Version: 1.0',
        'Content-Type: text/plain; charset=UTF-8',
        'Content-Transfer-Encoding: 8bit',
        'From: UmBaza Support <noreply@' . ($_SERVER['HTTP_HOST'] ?? 'umbaza.rf') . '>',
        'Reply-To: ' . $email,
    ];

    $ok = @mail($SUPPORT_TO, $subject, $bodyText, implode("\r\n", $headers));
    if (!$ok) {
        // Fall through to Render backend as a second attempt
    } else {
        http_response_code(200);
        echo json_encode([
            'ok' => true,
            'detail' => 'Сообщение отправлено на partners@умбаза.рф',
        ], JSON_UNESCAPED_UNICODE);
        exit;
    }
}

$target = rtrim($BACKEND, '/') . $path;
if ($query) {
    $target .= '?' . $query;
}

$headers = ['Content-Type: application/json'];
if (!empty($_SERVER['CONTENT_TYPE'])) {
    $headers = ['Content-Type: ' . $_SERVER['CONTENT_TYPE']];
}
if (!empty($_SERVER['HTTP_AUTHORIZATION'])) {
    $headers[] = 'Authorization: ' . $_SERVER['HTTP_AUTHORIZATION'];
}
if (!empty($_SERVER['HTTP_X_GUEST_ID'])) {
    $headers[] = 'X-Guest-Id: ' . $_SERVER['HTTP_X_GUEST_ID'];
}

$ch = curl_init($target);
curl_setopt_array($ch, [
    CURLOPT_CUSTOMREQUEST  => $method,
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_HEADER         => true,
    CURLOPT_HTTPHEADER     => $headers,
    CURLOPT_TIMEOUT        => 120,
    CURLOPT_FOLLOWLOCATION => false,
]);

if ($body !== '' && $body !== false) {
    curl_setopt($ch, CURLOPT_POSTFIELDS, $body);
}

$response = curl_exec($ch);
$httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
$headerSize = curl_getinfo($ch, CURLINFO_HEADER_SIZE);
curl_close($ch);

if ($response === false) {
    http_response_code(502);
    header('Content-Type: application/json');
    echo json_encode(['detail' => 'Backend unavailable']);
    exit;
}

$responseHeaders = substr($response, 0, $headerSize);
$responseBody = substr($response, $headerSize);

$contentType = 'application/json';
foreach (explode("\r\n", $responseHeaders) as $line) {
    if (stripos($line, 'Content-Type:') === 0) {
        $contentType = trim(substr($line, 13));
    }
}

http_response_code($httpCode);
header('Content-Type: ' . $contentType);
header('Cache-Control: no-store');
echo $responseBody;
