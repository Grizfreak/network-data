Shader "Custom/GPUIndirectURP"
{
    Properties
    {
        _BaseColor ("Base Color", Color) = (1,1,1,1)
    }

    SubShader
    {
        Tags
        {
            "RenderType"="Opaque"
            "Queue"="Geometry"
            "RenderPipeline"="UniversalPipeline"
        }

        Pass
        {
            Name "ForwardLit"

            HLSLPROGRAM

            #pragma vertex vert
            #pragma fragment frag
            #pragma target 4.5

            // Required for RenderMeshIndirect
            #define UNITY_INDIRECT_DRAW_ARGS IndirectDrawIndexedArgs
            #include "UnityIndirect.cginc"

            // URP includes
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            struct GPUIndirectMovement
            {
                float4 position_scale;
                float yaw;
                float isShown;
                float isMoving;
                float verticalVelocity;
            };

            StructuredBuffer<GPUIndirectMovement> _InstanceDataBuffer;

            float4 _BaseColor;

            struct Attributes
            {
                float3 positionOS : POSITION;
                float3 normalOS : NORMAL;
                uint vertexID : SV_VertexID;
                uint instanceID : SV_InstanceID;
            };

            struct Varyings
            {
                float4 positionHCS : SV_POSITION;
            };

            // Quaternion rotation helper
            float3 RotateVector(float3 v, float4 q)
            {
                return v + 2.0 * cross(q.xyz, cross(q.xyz, v) + q.w * v);
            }

            Varyings vert(Attributes IN)
            {
                Varyings OUT;

                // Required for indirect rendering
                InitIndirectDrawArgs(0);

                uint instanceIndex = GetIndirectInstanceID(IN.instanceID);

                GPUIndirectMovement data = _InstanceDataBuffer[instanceIndex];

                // Optional visibility toggle
                if (data.isShown < 0.5)
                {
                    OUT.positionHCS = float4(0,0,0,0);
                    return OUT;
                }

                float3 pos = IN.positionOS;

                // Scale
                pos *= data.position_scale.w;

                // Rotation
                float yawRad = radians(data.yaw);

                float s = sin(yawRad);
                float c = cos(yawRad);

                // Unity-style Y-axis rotation
                float3x3 rotY = float3x3(
                    c, 0, s,
                    0, 1, 0,
                    -s, 0, c
                );

                pos = mul(rotY, pos);

                // Translation
                pos += data.position_scale.xyz;
                OUT.positionHCS = TransformWorldToHClip(pos);

                return OUT;
            }

            half4 frag(Varyings IN) : SV_Target
            {
                return _BaseColor;
            }

            ENDHLSL
        }
    }
}