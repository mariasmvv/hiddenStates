using UnityEngine;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System;
using System.Text;

public class GameManager : MonoBehaviour
{
    [Header("Rocks")]
    public OrbManager rock0;
    public OrbManager rock1;

    [Header("Managers")]
    public TownLevelManager townLevelManager;
    public ForagingUI ui;

    [Header("Optional LSL (legacy)")]
    public LSLManager lsl;

    [Header("Pupil / Sync")]
    public PupilBridgeClient pupil;
    public bool usePupilEvents = true;

    [Header("── Laptop Network (EDIT THIS) ──")]
    [Tooltip("http://<laptop-LAN-IP>:<port>  e.g. http://192.168.1.42:8765")]
    public string laptopUrl = "http://192.168.1.50:8765";

    [Header("Session Structure")]
    public int totalLevels = 5;
    public float levelDuration = 300f;
    public float levelTransitionTime = 3f;

    [Header("Hidden State")]
    [Range(0f, 1f)] public float rewardProbability = 0.9f;
    [Range(0f, 1f)] public float depletionProbability = 0.3f;

    [Header("Gold (cosmetic incentive)")]
    public float goldPerReward = 10f;

    [Header("Participant / Output")]
    [Tooltip("Set this before pressing Play. Example: P001")]
    public string participantName = "TEST";

    [Tooltip("Optional custom root folder. Leave empty to use Application.persistentDataPath/SessionData")]
    public string outputRootFolder = "";

    [Header("Runtime State (read-only)")]
    [SerializeField] private int currentLevel = 1;
    [SerializeField] private float levelTimer = 0f;
    [SerializeField] private bool sessionActive = false;
    [SerializeField] private bool inTransition = false;
    [SerializeField] private int activeRock = 0;
    [SerializeField] private int depletionCount = 0;
    [SerializeField] private float totalGold = 0f;
    [SerializeField] private float levelGold = 0f;

    [SerializeField] private string sessionFolderName = "";
    [SerializeField] private string sessionFolderPath = "";
    [SerializeField] private string unityFolderPath = "";
    [SerializeField] private string pupilExportFolderPath = "";
    [SerializeField] private string derivedFolderPath = "";

    private long sessionStartNs = 0L;
    private int trialNumber = 0;
    private string saveTimestamp = "";

    private readonly List<TrialRecord> trialLog = new List<TrialRecord>();
    private readonly List<EventRecord> eventLog = new List<EventRecord>();

    [Serializable]
    public class TrialRecord
    {
        public int trial;
        public int level;
        public float levelTime;
        public float totalTime;
        public long unixTimeNs;
        public int rockChosen;
        public bool wasActiveRock;
        public bool rewarded;
        public bool depletionOccurred;
        public float goldGained;
        public float levelGold;
        public float totalGold;
        public int activeRockAfter;
        public int depletionCount;
    }

    [Serializable]
    public class EventRecord
    {
        public long unixTimeNs;
        public string eventType;
        public string payload;
    }

    void Awake()
    {
        if (ui == null) ui = FindObjectOfType<ForagingUI>();
        if (townLevelManager == null) townLevelManager = FindObjectOfType<TownLevelManager>();
        if (lsl == null) lsl = FindObjectOfType<LSLManager>();
        if (pupil == null) pupil = FindObjectOfType<PupilBridgeClient>();

        if (pupil != null)
            pupil.SetUrl(laptopUrl);

        if (rock0 == null || rock1 == null)
        {
            foreach (var r in FindObjectsOfType<OrbManager>())
            {
                if (r.rockID == 0) rock0 = r;
                if (r.rockID == 1) rock1 = r;
            }
        }

        if (rock0 == null) Debug.LogError("[GameManager] rock0 not found!");
        if (rock1 == null) Debug.LogError("[GameManager] rock1 not found!");
    }

    private IEnumerator Start()
    {
        if (pupil != null)
            yield return pupil.Initialize();

        StartSession();
    }

    void Update()
    {
        if (!sessionActive || inTransition) return;

        levelTimer += Time.deltaTime;
        ui?.UpdateTimer(Mathf.Max(0f, levelDuration - levelTimer));

        if (levelTimer >= levelDuration)
            StartCoroutine(TransitionToNextLevel());
    }

    public void StartSession()
    {
        sessionStartNs = GetNowUnixNs();
        saveTimestamp = DateTime.Now.ToString("yyyyMMdd_HHmmss");

        PrepareSessionFolders();

        currentLevel = 1;
        levelTimer = 0f;
        totalGold = 0f;
        levelGold = 0f;
        depletionCount = 0;
        trialNumber = 0;
        sessionActive = true;
        inTransition = false;

        trialLog.Clear();
        eventLog.Clear();

        LogAndSendEvent(
            "session_start",
            $"participant={participantName};rewardProb={rewardProbability:F2};depletionProb={depletionProbability:F2};totalLevels={totalLevels};levelDuration={levelDuration:F1}"
        );

        StartLevel(1);
        Debug.Log($"[GameManager] Session started. Folder: {sessionFolderPath}");
    }

    private void StartLevel(int level)
    {
        currentLevel = level;
        levelTimer = 0f;
        levelGold = 0f;
        depletionCount = 0;

        activeRock = UnityEngine.Random.value > 0.5f ? 0 : 1;
        ApplyActiveState();

        townLevelManager?.SetLevel(level);
        ui?.UpdateLevel(level, totalLevels);
        ui?.UpdateGold(0f);

        LogAndSendEvent(
            "level_start",
            $"level={level};activeRock={activeRock};rewardProb={rewardProbability:F2};depletionProb={depletionProbability:F2}"
        );

        Debug.Log($"[GameManager] Level {level} started. Active rock: {activeRock}");
    }

    private IEnumerator TransitionToNextLevel()
    {
        inTransition = true;
        sessionActive = false;

        LogAndSendEvent(
            "level_end",
            $"level={currentLevel};levelGold={levelGold:F2};totalGold={totalGold:F2};depletions={depletionCount}"
        );

        if (currentLevel >= totalLevels)
        {
            ui?.ShowMessage(
                $"Session Complete!\nThank you for helping Rustbucket!\nTotal Gold: {totalGold:F0}",
                0f
            );

            LogAndSendEvent(
                "session_end",
                $"totalGold={totalGold:F2};trials={trialNumber};levels={currentLevel}"
            );

            SaveTrialsOnly();

            Debug.Log("[GameManager] Session complete.");
            yield break;
        }

        ui?.ShowMessage($"Town upgraded!\nLevel {currentLevel + 1} incoming...", levelTransitionTime);

        yield return new WaitForSeconds(levelTransitionTime);

        sessionActive = true;
        inTransition = false;
        StartLevel(currentLevel + 1);
    }

    public void EndSession()
    {
        sessionActive = false;
        ui?.ShowMessage("Session ended.", 0f);

        LogAndSendEvent(
            "session_end_manual",
            $"totalGold={totalGold:F2};trials={trialNumber};level={currentLevel}"
        );

        SaveTrialsOnly();
    }

    private void ApplyActiveState()
    {
        rock0?.SetActiveState(activeRock == 0, rewardProbability, depletionProbability);
        rock1?.SetActiveState(activeRock == 1, rewardProbability, depletionProbability);
    }

    private void TriggerDepletion()
    {
        activeRock = activeRock == 0 ? 1 : 0;
        depletionCount++;
        ApplyActiveState();

        LogAndSendEvent(
            "depletion",
            $"count={depletionCount};newActiveRock={activeRock};level={currentLevel};levelTime={levelTimer:F3}"
        );

        Debug.Log($"[GameManager] Depletion #{depletionCount} — new active rock: {activeRock}");
    }

    public MiningResult ResolveMiningAttempt(int rockID)
    {
        if (!sessionActive || inTransition)
            return new MiningResult(false, 0f, false);

        bool wasActive = (rockID == activeRock);
        bool rewarded = false;
        bool depletionOccurred = false;
        float goldGained = 0f;

        if (wasActive)
        {
            rewarded = UnityEngine.Random.value < rewardProbability;
            depletionOccurred = UnityEngine.Random.value < depletionProbability;

            if (rewarded)
            {
                goldGained = goldPerReward;
                totalGold += goldGained;
                levelGold += goldGained;
                ui?.UpdateGold(levelGold);
            }

            if (depletionOccurred)
                TriggerDepletion();
        }

        trialNumber++;
        float totalTime = (currentLevel - 1) * levelDuration + levelTimer;
        long nowNs = GetNowUnixNs();

        trialLog.Add(new TrialRecord
        {
            trial = trialNumber,
            level = currentLevel,
            levelTime = levelTimer,
            totalTime = totalTime,
            unixTimeNs = nowNs,
            rockChosen = rockID,
            wasActiveRock = wasActive,
            rewarded = rewarded,
            depletionOccurred = depletionOccurred,
            goldGained = goldGained,
            levelGold = levelGold,
            totalGold = totalGold,
            activeRockAfter = activeRock,
            depletionCount = depletionCount
        });

        LogAndSendEvent(
            "trial",
            $"trial={trialNumber};level={currentLevel};levelTime={levelTimer:F3};totalTime={totalTime:F3};rock={rockID};wasActive={wasActive};rewarded={rewarded};depleted={depletionOccurred};goldGained={goldGained:F2};levelGold={levelGold:F2};totalGold={totalGold:F2};activeRockAfter={activeRock};depletionCount={depletionCount}"
        );

        Debug.Log($"[GameManager] Trial {trialNumber} L{currentLevel}: Rock {rockID} active={wasActive} reward={rewarded} depleted={depletionOccurred} gold={totalGold:F0}");

        return new MiningResult(rewarded, goldGained, depletionOccurred);
    }

    public void LogExternalEvent(string eventType, string payload)
    {
        LogAndSendEvent(eventType, payload);
    }

    private void LogAndSendEvent(string eventType, string payload)
    {
        long nowNs = GetNowUnixNs();

        eventLog.Add(new EventRecord
        {
            unixTimeNs = nowNs,
            eventType = eventType,
            payload = payload
        });

        if (usePupilEvents && pupil != null && pupil.IsSyncReady)
            pupil.SendEvent($"{eventType};{payload}");
    }

    private long GetNowUnixNs()
    {
        if (pupil != null && pupil.IsSyncReady)
            return pupil.NowNs();

        return DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() * 1_000_000L;
    }

    private void PrepareSessionFolders()
    {
        string cleanParticipant = SanitizePathComponent(participantName);
        if (string.IsNullOrWhiteSpace(cleanParticipant))
            cleanParticipant = "UNKNOWN";

        string root = outputRootFolder;
        if (string.IsNullOrWhiteSpace(root))
            root = Path.Combine(Application.persistentDataPath, "SessionData");

        sessionFolderName = $"{cleanParticipant}_{saveTimestamp}";
        sessionFolderPath = Path.Combine(root, sessionFolderName);
        unityFolderPath = Path.Combine(sessionFolderPath, "unity");
        pupilExportFolderPath = Path.Combine(sessionFolderPath, "pupil_export");
        derivedFolderPath = Path.Combine(sessionFolderPath, "derived");

        Directory.CreateDirectory(root);
        Directory.CreateDirectory(sessionFolderPath);
        Directory.CreateDirectory(unityFolderPath);
        Directory.CreateDirectory(pupilExportFolderPath);
        Directory.CreateDirectory(derivedFolderPath);

        WriteSessionReadme();
    }

    private void WriteSessionReadme()
    {
        string path = Path.Combine(sessionFolderPath, "README.txt");

        var sb = new StringBuilder();
        sb.AppendLine($"Participant: {participantName}");
        sb.AppendLine($"Session folder: {sessionFolderName}");
        sb.AppendLine($"Created: {DateTime.Now:yyyy-MM-dd HH:mm:ss}");
        sb.AppendLine();
        sb.AppendLine("Place exported Pupil files inside:");
        sb.AppendLine("  pupil_export/");
        sb.AppendLine();
        sb.AppendLine("Expected files:");
        sb.AppendLine("  events.csv");
        sb.AppendLine("  gaze.csv");
        sb.AppendLine("  world.mp4");
        sb.AppendLine();
        sb.AppendLine("Derived outputs will be written to:");
        sb.AppendLine("  derived/");

        File.WriteAllText(path, sb.ToString());
    }

    private string BuildTrialsCsv()
    {
        var sb = new StringBuilder();
        sb.AppendLine($"# participant={participantName}");
        sb.AppendLine($"# session_folder={sessionFolderName}");
        sb.AppendLine($"# session_start_ns={sessionStartNs}");
        sb.AppendLine("trial;level;levelTime;totalTime;unixTimeNs;rockChosen;wasActiveRock;rewarded;depletionOccurred;goldGained;levelGold;totalGold;activeRockAfter;depletionCount");

        foreach (var r in trialLog)
        {
            sb.AppendLine(
                $"{r.trial};{r.level};{r.levelTime:F3};{r.totalTime:F3};{r.unixTimeNs};" +
                $"{r.rockChosen};{r.wasActiveRock};{r.rewarded};{r.depletionOccurred};" +
                $"{r.goldGained:F2};{r.levelGold:F2};{r.totalGold:F2};{r.activeRockAfter};{r.depletionCount}"
            );
        }

        return sb.ToString();
    }

    private void SaveTrialsOnly()
    {
        string trialsCsv = BuildTrialsCsv();
        string trialsFilename = $"{sessionFolderName}_trials.csv";
        string trialsPath = Path.Combine(unityFolderPath, trialsFilename);

        try
        {
            File.WriteAllText(trialsPath, trialsCsv);
            Debug.Log($"[GameManager] Saved trials to: {trialsPath}");
        }
        catch (Exception e)
        {
            Debug.LogWarning($"[GameManager] Could not write trials CSV: {e.Message}");
        }
    }

    private string SanitizePathComponent(string raw)
    {
        if (string.IsNullOrWhiteSpace(raw))
            return "";

        string clean = raw.Trim();

        foreach (char c in Path.GetInvalidFileNameChars())
            clean = clean.Replace(c.ToString(), "");

        clean = clean.Replace(" ", "_");
        return clean;
    }

    public string SessionFolderPath => sessionFolderPath;
    public string SessionFolderName => sessionFolderName;
    public string UnityFolderPath => unityFolderPath;
    public string PupilExportFolderPath => pupilExportFolderPath;
    public string DerivedFolderPath => derivedFolderPath;

    public bool IsSessionActive => sessionActive && !inTransition;
    public int ActiveRock => activeRock;
    public float TotalGold => totalGold;
    public float LevelGold => levelGold;
    public float GoldPerReward => goldPerReward;
    public int CurrentLevel => currentLevel;
    public int TotalLevels => totalLevels;
    public float LevelTimeRemaining => Mathf.Max(0f, levelDuration - levelTimer);
    public float CurrentLevelElapsedTime => levelTimer;
}

public struct MiningResult
{
    public bool rewarded;
    public float goldGained;
    public bool depletionOccurred;

    public MiningResult(bool rewarded, float goldGained, bool depletionOccurred)
    {
        this.rewarded = rewarded;
        this.goldGained = goldGained;
        this.depletionOccurred = depletionOccurred;
    }
}