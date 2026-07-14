<?php
/**
 * Proxies /api/* requests to the Render backend.
 * Keeps the frontend and API on the same origin (no CORS issues).
 */
$BACKEND = 'https://edusynth.onrender.com';

$uri = $_SERVER['REQUEST_URI'];
$path = parse_url($uri, PHP_URL_PATH);
$query = parse_url($uri, PHP_URL_QUERY);

$target = rtrim($BACKEND, '/') . $path;
if ($query) {
    $target .= '?' . $query;
}

$method = $_SERVER['REQUEST_METHOD'];
$body = file_get_contents('php://input');

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
