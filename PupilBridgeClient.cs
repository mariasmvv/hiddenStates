using System;
using System.Collections;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;
using Stopwatch = System.Diagnostics.Stopwatch;

/// <summary>
/// Talks to bridge.py running on the laptop.
///
/// SETUP:
///   1. Set bridgeUrl to http://<laptop-IP>:8765
///   2. Attach to any GameObject — GameManager finds it automatically
///   3. Start bridge.py on the laptop BEFORE pressing Play
///
/// How it works:
///   - On Start, calls /sync a few times to measure Quest↔laptop clock offset
///   - Every event call computes the corrected Companion timestamp and POSTs to /event
///   - bridge.py injects the event into the Pupil recording at the right time
/// </summary>
public class PupilBridgeClient : MonoBehaviour
{
    // ── SET THIS TO YOUR LAPTOP'S LOCAL IP + PORT ──────────────
    //   Format:  http://<laptop-IP>:<port>
    //   Example: http://192.168.1.42:8765
    //
    //   To find your laptop IP on Windows:  run  ipconfig  → IPv4 Address
    //   To find your laptop IP on Mac/Linux: run  ifconfig  → inet
    //   The port must match the port bridge.py is listening on (default 8765).
    // ──────────────────────────────────────────────────────────
    [Header("── Laptop IP & Port (EDIT THIS) ──")]
    public string bridgeUrl = "http://192.168.137.1:8765";

    /// <summary>Call from GameManager.Awake() to set URL from one central place.</summary>
    public void SetUrl(string url) { bridgeUrl = url; }

    [Header("Sync")]
    [Tooltip("Number of round-trips to measure. More = more accurate, slower start.")]
    public int syncSamples = 10;

    // ── Runtime (Inspector-readable) ──────────
    [Header("Runtime (read-only)")]
    [SerializeField] private bool syncReady = false;
    [SerializeField] private float offsetMs = 0f;   // quest - companion in ms
    [SerializeField] private float rttMs = 0f;

    // ── Internal clock ────────────────────────
    private long unixOriginNs;
    private long swOriginTicks;

    // ── Offset: subtract from Quest ns to get Companion ns ──
    private long questMinusCompanionNs = 0;

    public bool IsSyncReady => syncReady;

    // ─────────────────────────────────────────
    //  Awake — set up a high-res clock anchored to Unix time
    // ─────────────────────────────────────────
    void Awake()
    {
        if (FindObjectsOfType<PupilBridgeClient>().Length > 1)
    {
        Destroy(gameObject);
        return;
    }
        DontDestroyOnLoad(gameObject);
        unixOriginNs  = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() * 1_000_000L;
        swOriginTicks = Stopwatch.GetTimestamp();

        StartCoroutine(Initialize());
    }

    // ─────────────────────────────────────────
    //  Public: current Quest time as Unix ns
    // ─────────────────────────────────────────
    public long NowNs()
    {
        long elapsed = Stopwatch.GetTimestamp() - swOriginTicks;
        double ns = (double)elapsed * 1_000_000_000.0 / Stopwatch.Frequency;
        return unixOriginNs + (long)Math.Round(ns);
    }

    // ─────────────────────────────────────────
    //  Sync — call this as a coroutine and wait for it
    //  GameManager already does:  yield return pupil.Initialize();
    // ─────────────────────────────────────────
    public IEnumerator Initialize()
    {
        yield return SyncClocks();
    }

    private IEnumerator SyncClocks()
    {
        long bestRtt = long.MaxValue;
        long bestOffset = 0;
        int successes = 0;

        for (int i = 0; i < syncSamples; i++)
        {
            long t0 = NowNs();

            using var req = UnityWebRequest.Get($"{bridgeUrl}/sync");
            req.timeout = 3;
            yield return req.SendWebRequest();

            long t3 = NowNs();

            if (req.result != UnityWebRequest.Result.Success)
            {
                Debug.LogWarning($"[PupilBridge] Sync sample {i} failed: {req.error}");
                continue;
            }

            var r = JsonUtility.FromJson<SyncResp>(req.downloadHandler.text);
            if (r == null || !r.ok) continue;

            long serverMid  = (r.server_receive_ns + r.server_send_ns) / 2L;
            long clientMid  = (t0 + t3) / 2L;
            long rtt        = t3 - t0 - (r.server_send_ns - r.server_receive_ns);
            long qMinusHost = clientMid - serverMid;

            if (rtt < bestRtt)
            {
                bestRtt    = rtt;
                // quest_minus_companion = quest_minus_host + host_minus_companion
                bestOffset = qMinusHost + r.host_minus_companion_ns;
            }

            successes++;
            yield return null;
        }

        if (successes == 0)
        {
            Debug.LogError("[PupilBridge] Sync failed — is bridge.py running on the laptop?");
            yield break;
        }

        questMinusCompanionNs = bestOffset;
        syncReady = true;
        offsetMs  = (float)(questMinusCompanionNs / 1_000_000.0);
        rttMs     = (float)(bestRtt / 1_000_000.0);

        Debug.Log($"[PupilBridge] Sync OK | offset={offsetMs:F2} ms | rtt={rttMs:F2} ms");
    }

    // ─────────────────────────────────────────
    //  Send an event — fire and forget
    // ─────────────────────────────────────────
    public void SendEvent(string name)
    {
        if (!syncReady)
        {
            Debug.LogWarning("[PupilBridge] SendEvent called before sync ready.");
            return;
        }
        StartCoroutine(PostEvent(name));
    }

    private IEnumerator PostEvent(string name)
    {
        long questNs     = NowNs();
        long companionNs = questNs - questMinusCompanionNs;

        var payload = new EventPayload
        {
            name                  = name,
            companion_timestamp_ns = companionNs,
        };

        byte[] body = Encoding.UTF8.GetBytes(JsonUtility.ToJson(payload));

        using var req = new UnityWebRequest($"{bridgeUrl}/event", "POST");
        req.uploadHandler   = new UploadHandlerRaw(body);
        req.downloadHandler = new DownloadHandlerBuffer();
        req.SetRequestHeader("Content-Type", "application/json");
        req.timeout = 3;

        yield return req.SendWebRequest();

        if (req.result != UnityWebRequest.Result.Success)
            Debug.LogWarning($"[PupilBridge] Event failed: {req.error}");
    }

    // ─────────────────────────────────────────
    //  JSON structs
    // ─────────────────────────────────────────
    [Serializable] private class SyncResp
    {
        public bool ok;
        public long server_receive_ns;
        public long server_send_ns;
        public long host_minus_companion_ns;
    }

    [Serializable] private class EventPayload
    {
        public string name;
        public long   companion_timestamp_ns;
    }
}