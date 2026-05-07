using UnityEngine;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System;
using System.Text;

public class GameManager : MonoBehaviour
{
    private static GameManager _instance;

    [Header("Automation")]
    public bool quitApplicationOnSessionEnd = true;
    public float quitDelaySeconds = 3f;

    [Header("Rocks")]
    public OrbManager rock0;
    public OrbManager rock1;

    [Header("Managers")]
    public TownLevelManager townLevelManager;
    public ForagingUI ui;

    [Header("Pupil / Sync")]
    public PupilBridgeClient pupil;
    public bool usePupilEvents = true;

    [Header("── Laptop Network (EDIT THIS) ──")]
    public string laptopUrl = "http://192.168.1.50:8765";

    [Header("Session Structure")]
    public int totalLevels = 5;
    public float levelDuration = 300f;
    public float levelTransitionTime = 3f;

    [Header("Hidden State")]
    [Range(0f, 1f)] public float rewardProbability = 0.9f;
    [Range(0f, 1f)] public float depletionProbability = 0.3f;

    [Header("Gold")]
    public float goldPerReward = 10f;

    [Header("Participant / Output")]
    public string participantName = "TEST";
    public string outputRootFolder = "";

    [Header("Runtime State")]
    [SerializeField] private int currentLevel = 1;
    [SerializeField] private float levelTimer = 0f;
    [SerializeField] private bool sessionActive = false;
    [SerializeField] private bool inTransition = false;

    [SerializeField] private bool rock0Active = true;
    [SerializeField] private bool rock1Active = false;

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

    public string[] levelResources = { "Gold", "Water", "Crystals", "Rock", "Wood" };

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
        public bool rock0Flipped;
        public bool rock1Flipped;
        public bool anyFlipOccurred;
        public float goldGained;
        public float levelGold;
        public float totalGold;
        public bool rock0ActiveAfter;
        public bool rock1ActiveAfter;
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
        // 1. SINGLETON: Only one GameManager can exist
        if (_instance != null && _instance != this)
        {
            Destroy(gameObject);
            return;
        }
        _instance = this;
        DontDestroyOnLoad(gameObject); // 2. PERSISTENCE: Stay alive between scenes

        // Auto-find references if missing
        if (ui == null) ui = FindObjectOfType<ForagingUI>();
        if (townLevelManager == null) townLevelManager = FindObjectOfType<TownLevelManager>();
        if (pupil == null) pupil = FindObjectOfType<PupilBridgeClient>();

        if (pupil != null)
            pupil.SetUrl(laptopUrl);

        FindRocksInScene();
    }

    private void OnEnable() => UnityEngine.SceneManagement.SceneManager.sceneLoaded += OnSceneLoaded;
    private void OnDisable() => UnityEngine.SceneManagement.SceneManager.sceneLoaded -= OnSceneLoaded;

private void OnSceneLoaded(UnityEngine.SceneManagement.Scene scene, UnityEngine.SceneManagement.LoadSceneMode mode)
{
    // Re-find references for the new scene
    FindRocksInScene();
    ui = FindObjectOfType<ForagingUI>();

    // ONLY start the session if we have transitioned to Level1
    if (scene.name == "Level1" && !sessionActive)
    {
        StartSession();
    }

    ui?.UpdateGold(totalGold);
    ui?.UpdateLevel(currentLevel);
    ui?.UpdateResourceLabel(CurrentResourceName, levelGold);
}

    private void LoadParticipantNameFromDashboard()
{
    // 1. Try to use the path assigned in the Inspector
    string configPath = Path.Combine(outputRootFolder, "next_session_config.txt");

    // 2. If the Inspector field is empty, fallback to the default path
    if (string.IsNullOrEmpty(outputRootFolder))
    {
        // FIX: Added 'string' here so the variable 'root' is properly declared
        string root = Path.Combine(Application.persistentDataPath, "SessionData");
        configPath = Path.Combine(root, "next_session_config.txt");
    }

    if (File.Exists(configPath))
    {
        try
        {
            string name = File.ReadAllText(configPath).Trim();
            if (!string.IsNullOrEmpty(name))
            {
                this.participantName = name;
                Debug.Log($"[GameManager] Participant name updated from dashboard: {name}");
                
                // Delete the file so it doesn't reuse the name next time
                File.Delete(configPath);
            }
        }
        catch (Exception e)
        {
            Debug.LogError($"Failed to read dashboard config: {e.Message}");
        }
    }
}

    private void FindRocksInScene()
    {
        rock0 = null;
        rock1 = null;
        foreach (var r in FindObjectsOfType<OrbManager>())
        {
            if (r.rockID == 0) rock0 = r;
            if (r.rockID == 1) rock1 = r;
        }
    }

    private IEnumerator Start()
    {
        if (pupil != null)
            yield return pupil.Initialize();
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
        // 1. SYNC NAME FIRST: Look for the dashboard file before doing anything else
        LoadParticipantNameFromDashboard();

        // 2. NOW SET TIMESTAMPS: These will be used for the folder name
        sessionStartNs = GetNowUnixNs();
        saveTimestamp = DateTime.Now.ToString("yyyyMMdd_HHmmss");

        // 3. GENERATE PATHS: This now uses the name we just pulled from the dashboard
        PrepareSessionFolders();

        // 4. RESET STATE
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

        // 5. LOG START: The event payload will now show the correct participantName
        LogAndSendEvent(
            "session_start",
            $"participant={participantName};rewardProb={rewardProbability:F2};flipProb={depletionProbability:F2};totalLevels={totalLevels};levelDuration={levelDuration:F1}"
        );

        SaveTrialsOnly();

        StartLevel(1);

        Debug.Log($"[GameManager] Session started. Folder: {sessionFolderPath}");
    }

    private void StartLevel(int level)
    {
        currentLevel = level;
        levelTimer = 0f;
        levelGold = 0f;
        depletionCount = 0;

        rock0Active = UnityEngine.Random.value > 0.5f;
        rock1Active = !rock0Active;

        ApplyActiveState();

        townLevelManager?.SetLevel(level);
        ui?.UpdateLevel(level);
        ui?.UpdateGold(0f);
        ui?.UpdateGoldBar(0f);
        ui?.UpdateResourceLabel(CurrentResourceName, 0f); 

        LogAndSendEvent(
            "level_start",
            $"level={level};rock0Active={rock0Active};rock1Active={rock1Active};rewardProb={rewardProbability:F2};flipProb={depletionProbability:F2}"
        );

        Debug.Log($"[GameManager] Level {level} started. rock0Active={rock0Active}, rock1Active={rock1Active}");
    }

    private IEnumerator TransitionToNextLevel()
    {
        inTransition = true;
        sessionActive = false;

        LogAndSendEvent(
            "level_end",
            $"level={currentLevel};levelGold={levelGold:F2};totalGold={totalGold:F2};flips={depletionCount}"
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

            if (quitApplicationOnSessionEnd)
            {
                Debug.Log($"[GameManager] Quitting application in {quitDelaySeconds} seconds...");
                yield return new WaitForSeconds(quitDelaySeconds);
                Application.Quit();
            }

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

    public string CurrentResourceName => levelResources[Mathf.Clamp(currentLevel - 1, 0, levelResources.Length - 1)];

    private void ApplyActiveState()
    {
        rock0?.SetActiveState(rock0Active, rewardProbability, depletionProbability);
        rock1?.SetActiveState(rock1Active, rewardProbability, depletionProbability);
    }

    public MiningResult ResolveMiningAttempt(int rockID)
    {
        if (!sessionActive || inTransition)
            return new MiningResult(false, 0f, false);

        bool wasActive = rockID == 0 ? rock0Active : rock1Active;
        bool rewarded = false;
        float goldGained = 0f;

        if (wasActive)
        {
            rewarded = UnityEngine.Random.value < rewardProbability;

            if (rewarded)
            {
                goldGained = goldPerReward;
                totalGold += goldGained;
                levelGold += goldGained;
                ui?.UpdateResourceLabel(CurrentResourceName, levelGold);
                ui?.ShowRewardMessage($"+{goldGained:F0} {CurrentResourceName}!", totalGold);
            }
        }

        bool systemFlipped = UnityEngine.Random.value < depletionProbability;

        if (systemFlipped)
        {
            // Inverte ambas simultaneamente
            rock0Active = !rock0Active;
            rock1Active = !rock1Active;
            depletionCount++;

            LogAndSendEvent(
                "depletion",
                $"count={depletionCount};systemFlipped=true;rock0Active={rock0Active};rock1Active={rock1Active}"
            );
        }

        ApplyActiveState();

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
            anyFlipOccurred = systemFlipped,
            goldGained = goldGained,
            levelGold = levelGold,
            totalGold = totalGold,
            rock0ActiveAfter = rock0Active,
            rock1ActiveAfter = rock1Active,
            depletionCount = depletionCount
        });

        LogAndSendEvent(
            "trial",
            $"trial={trialNumber};level={currentLevel};levelTime={levelTimer:F3};totalTime={totalTime:F3};rock={rockID};wasActive={wasActive};rewarded={rewarded};anyFlipOccurred={systemFlipped};goldGained={goldGained:F2};levelGold={levelGold:F2};totalGold={totalGold:F2};rock0ActiveAfter={rock0Active};rock1ActiveAfter={rock1Active};depletionCount={depletionCount}"
        );

        Debug.Log($"[GameManager] Trial {trialNumber} L{currentLevel}: Rock {rockID} active={wasActive} reward={rewarded} anyFlipOccurred={systemFlipped}");


        SaveTrialsOnly(); 
        return new MiningResult(rewarded, goldGained, systemFlipped);
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
        sb.AppendLine("trial;level;levelTime;totalTime;unixTimeNs;rockChosen;wasActiveRock;rewarded;rock0Flipped;rock1Flipped;anyFlipOccurred;goldGained;levelGold;totalGold;rock0ActiveAfter;rock1ActiveAfter;depletionCount");

        foreach (var r in trialLog)
        {
            sb.AppendLine(
                $"{r.trial};{r.level};{r.levelTime:F3};{r.totalTime:F3};{r.unixTimeNs};" +
                $"{r.rockChosen};{r.wasActiveRock};{r.rewarded};" +
                $"{r.rock0Flipped};{r.rock1Flipped};{r.anyFlipOccurred};" +
                $"{r.goldGained:F2};{r.levelGold:F2};{r.totalGold:F2};" +
                $"{r.rock0ActiveAfter};{r.rock1ActiveAfter};{r.depletionCount}"
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

    public bool Rock0Active => rock0Active;
    public bool Rock1Active => rock1Active;

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