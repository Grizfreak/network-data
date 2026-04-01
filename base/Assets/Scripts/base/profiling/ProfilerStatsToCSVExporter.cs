using System;
using System.Globalization;
using System.IO;
using UnityEngine;

namespace Unity.Profiling
{
	/// <summary>
	/// This component will export the specified Profiler stats to a CSV file in the application persistent data path
	/// cf. https://docs.unity3d.com/ScriptReference/Unity.Profiling.ProfilerRecorder.html
	/// </summary>
	public class ProfilerStatsToCSVExporter : MonoBehaviour
	{
		[Serializable]
		private sealed class ProfilerStatsEntry
		{
			public string Category;
			public string Name;
			
			public ProfilerStatsEntry(string category, string name)
			{
				Category = category;
				Name = name;
			}
			
			public ProfilerRecorder ToProfilerRecorder()
			{
				ProfilerCategory profilerCategory = new ProfilerCategory(Category);
				return ProfilerRecorder.StartNew(profilerCategory, Name);
			}
		}
		
		private const char OUTPUT_SEPARATOR = ',';
		
		[SerializeField] [Tooltip("Input values found via ProfilerRecorderHandle.GetAvailable")]
		private ProfilerStatsEntry[] profilerStats = { 
			new ("GC", "GC.Collect"),
			new ("Internal", "Main Thread"),
			new ("Memory", "Total Used Memory"),
			new ("Memory", "Audio Used Memory"),
			new ("Memory", "GC Used Memory"),
			new ("PlayerLoop", "PlayerLoop"),
			new ("Render", "Batches Count"),
			new ("Render", "CPU Main Thread Frame Time"),
			new ("Render", "CPU Render Thread Frame Time"),
			new ("Render", "CPU Total Frame Time"),
			new ("Render", "Draw Calls Count"),
			new ("Render", "FrameTime.GPU"),
			new ("Render", "GPU Frame Time"),
			new ("Render", "Gfx.WaitForPresentOnGfxThread"),
			new ("Render", "Render Textures Bytes"),
			new ("Render", "Render Textures Count"),
			new ("Render", "SetPass Calls Count"),
			new ("Render", "Shadow Casters Count"),
			new ("Render", "Triangles Count"),
			new ("Render", "Vertices Count"),
			new ("VSync", "WaitForTargetFPS")
		};
		
		private TextWriter _textWriter;
		private ProfilerRecorder[] _profilerRecorders;
		private float _lastFlushTime;

		// Record FPS within the app
		private float _accumulatedTime;
		private int _frameCounter;
		private float _lastComputedFps = 0f;
		
		private void OnEnable()
		{
			string outputFilePath = Path.Combine(Application.persistentDataPath, $"profiler_stats-{DateTime.Now:yyyy.MM.dd-HH.mm}.csv");
			_textWriter = new StreamWriter(outputFilePath, true);
			
			Debug.Log("Writing Profiler Stats to " + outputFilePath);
			
			_textWriter.Write("Frame");
			_textWriter.Write(OUTPUT_SEPARATOR);
			
			// FPS Column
			_textWriter.Write("FPS");
			_textWriter.Write(OUTPUT_SEPARATOR);
			
			// Frame Time
			_textWriter.Write("FrameTimeMs");
			_textWriter.Write(OUTPUT_SEPARATOR);
			
			_profilerRecorders = new ProfilerRecorder[profilerStats.Length];
			for (int i = 0; i < profilerStats.Length; i++)
			{
				_profilerRecorders[i] = profilerStats[i].ToProfilerRecorder();
				
				if (_profilerRecorders[i].Valid == false)
				{
					Debug.LogError($"ProfilerRecorder for {profilerStats[i].Name} ({profilerStats[i].Category}) is not valid. Either there's a typo or this ProfilerRecorder is not available on this platform.");
					continue;
				}
				
				_textWriter.Write(profilerStats[i].Name);
				AppendStatUnitToText(_profilerRecorders[i], _textWriter);
				
				bool isLastColumn = i == profilerStats.Length - 1;
				AppendSeparatorToText(_textWriter, isLastColumn);
			}
		}

		private void OnDisable()
		{
			_textWriter.Flush();
			_textWriter.Dispose();

			foreach (ProfilerRecorder profilerRecorder in _profilerRecorders)
			{
				profilerRecorder.Dispose();
			}
		}

		private void Update()
		{
			float frameTimeMs = Time.unscaledDeltaTime * 1000f;
			// FPS Recording
			_accumulatedTime += Time.unscaledDeltaTime;
			_frameCounter++;

			if (_accumulatedTime >= 1f)
			{
				_lastComputedFps = _frameCounter / _accumulatedTime;

				_accumulatedTime = 0f;
				_frameCounter = 0;
			}
			
			_textWriter.Write(GetLongAsChars(Time.frameCount));
			_textWriter.Write(OUTPUT_SEPARATOR);

			// FPS value
			_textWriter.Write(_lastComputedFps.ToString(CultureInfo.InvariantCulture));
			_textWriter.Write(OUTPUT_SEPARATOR);
			
			// Frame time
			_textWriter.Write(frameTimeMs.ToString(CultureInfo.InvariantCulture));
			_textWriter.Write(OUTPUT_SEPARATOR);

			for (int i = 0; i < _profilerRecorders.Length; i++)
			{
				ProfilerRecorder profilerRecorder = _profilerRecorders[i];
				_textWriter.Write(GetLongAsChars(profilerRecorder.LastValue));
				
				bool isLastColumn = i == _profilerRecorders.Length - 1;
				AppendSeparatorToText(_textWriter, isLastColumn);
			}

			if (_lastFlushTime + 1f < Time.realtimeSinceStartup)
			{
				_lastFlushTime = Time.realtimeSinceStartup;
				_textWriter.Flush();
			}
		}
		
		private static void AppendSeparatorToText(TextWriter textWriter, bool isLastColumn = false)
		{
			if (isLastColumn)
			{
				textWriter.WriteLine();
			}
			else
			{
				textWriter.Write(OUTPUT_SEPARATOR);
			}
		}

		private static void AppendStatUnitToText(ProfilerRecorder profilerRecorder, TextWriter textWriter)
		{
			switch (profilerRecorder.UnitType)
			{
				case ProfilerMarkerDataUnit.TimeNanoseconds:
					textWriter.Write(" (ns)");
					break;
					
				case ProfilerMarkerDataUnit.Bytes:
					textWriter.Write(" (bytes)");
					break;
					
				case ProfilerMarkerDataUnit.Percent:
					textWriter.Write(" (%)");
					break;
					
				case ProfilerMarkerDataUnit.FrequencyHz:
					textWriter.Write(" (Hz)");
					break;
					
				case ProfilerMarkerDataUnit.Undefined:
				case ProfilerMarkerDataUnit.Count:
				default:
					break;
			}
		}
		
		private static readonly char[] _longAsCharsBuffer = new char[20]; // 19 for long.MaxValue.ToString().Length + 1 for negative sign
		private static ReadOnlySpan<char> GetLongAsChars(long value)
		{
			int bufferIndex = 0;
			if (value == 0) 
			{
				_longAsCharsBuffer[bufferIndex] = '0';
				return new Span<char>(_longAsCharsBuffer, bufferIndex, 1);
			}
			
			// For negative values, we need to add the '-' sign and invert the value
			if (value < 0)
			{
				_longAsCharsBuffer[bufferIndex] = '-';
				bufferIndex++;
				value = -value;
			}
			
			int length = 1;
			for (long r = value / 10; r > 0; r /= 10)
			{
				length++;
			}
			
			for (int i = length - 1; i >= 0; i--)
			{
				_longAsCharsBuffer[bufferIndex + i] = (char)('0' + (value % 10));
				value /= 10;
			}

			ReadOnlySpan<char> bufferSplice = new ReadOnlySpan<char>(_longAsCharsBuffer).Slice(bufferIndex, length);
			return bufferSplice;
		}
	}
}